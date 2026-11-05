import pyfiglet
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.markup import escape

import os.path
import base64
import html
import re
import math
from pathlib import Path
from datetime import datetime, timedelta, timezone
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from oauthlib.oauth2.rfc6749.errors import AccessDeniedError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import nltk
from nltk.corpus import stopwords
from nltk.probability import FreqDist
from nltk.tokenize import sent_tokenize

console = Console()

ascii_arte = pyfiglet.figlet_format("GAIA", font="banner")
console.print(Panel(ascii_arte, title="GAIA", border_style="blue"))
console.print("Digite a opção para rodar a rotina descrita:")

N_FRASES_RESUMO = 3


def _garantir_recursos_nltk():
    for recurso in ("punkt_tab", "punkt", "stopwords"):
        try:
            nltk.data.find(f"tokenizers/{recurso}")
        except LookupError:
            nltk.download(recurso, quiet=True)


_garantir_recursos_nltk()


# ============================================================
# Lista negra
# ============================================================

def carregar_lista_negra():
    if not Path("lista_negra.json").is_file():
        return []
    try:
        return json.load(open("lista_negra.json", encoding="utf-8"))
    except Exception:
        return []


def salvar_lista_negra(lista):
    with open("lista_negra.json", "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)


def extrair_email(remetente):
    m = re.search(r"<([^>]+)>", remetente)
    return (m.group(1) if m else remetente).strip().lower()


def esta_bloqueado(remetente, lista_negra):
    if not lista_negra:
        return False
    email = extrair_email(remetente)
    for item in lista_negra:
        item = item.strip().lower()
        if not item:
            continue
        if item.startswith("@"):
            if email.endswith(item):
                return True
        elif email == item:
            return True
    return False


# ============================================================
# Extração e NLP
# ============================================================

def obter_header(payload, nome):
    for h in payload.get("headers", []):
        if h.get("name", "").lower() == nome.lower():
            return h.get("value", "")
    return ""


def decodificar_base64url(dados):
    if not dados:
        return ""
    try:
        return base64.urlsafe_b64decode(dados + "=" * (-len(dados) % 4)).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _coletar_textos(payload, lista_plain, lista_html):
    mime = payload.get("mimeType", "text/plain")
    body_data = payload.get("body", {}).get("data")
    if mime == "text/plain" and body_data:
        lista_plain.append(decodificar_base64url(body_data))
    elif mime == "text/html" and body_data:
        lista_html.append(decodificar_base64url(body_data))
    for parte in payload.get("parts", []):
        _coletar_textos(parte, lista_plain, lista_html)


def limpar_html(texto_html):
    texto = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", texto_html)
    texto = re.sub(r"(?s)<[^>]+>", " ", texto)
    texto = html.unescape(texto)
    return texto


def extrair_texto_email(msg):
    lista_plain, lista_html = [], []
    _coletar_textos(msg.get("payload", {}), lista_plain, lista_html)
    texto = "\n".join(lista_plain).strip()
    if len(texto) < 50 and lista_html:
        texto = limpar_html("\n".join(lista_html))
    return texto


def limpar_texto(texto):
    texto = re.split(r"(?im)\n\s*(em 20\d\d.*escreveu:|on .*wrote:|--?\s*$|para sua segurança.*cancele|enviado do meu iphone)", texto)[0]
    texto = re.sub(r"https?://\S+", " ", texto)
    linhas = [l.strip() for l in texto.splitlines() if any(c.isalpha() for c in l)]
    texto = " ".join(linhas)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def detectar_idioma(texto):
    texto_lower = " " + texto.lower() + " "
    palavras_pt = [" de ", " que ", " para ", " com ", " você ", " obrigado", " não ", " este ", " esta "]
    palavras_en = [" the ", " and ", " for ", " with ", " you ", " thank", " this ", " that ", " are "]
    score_pt = sum(texto_lower.count(p) for p in palavras_pt)
    score_en = sum(texto_lower.count(p) for p in palavras_en)
    return "english" if score_en > score_pt else "portuguese"


def gerar_resumo_extrativo(texto, n_frases=N_FRASES_RESUMO):
    texto = limpar_texto(texto)
    if not texto or len(texto) < 30:
        return texto[:500], detectar_idioma(texto)

    idioma = detectar_idioma(texto)
    try:
        frases = sent_tokenize(texto, language=idioma)
    except Exception:
        frases = sent_tokenize(texto)

    frases_validas = [f.strip() for f in frases if 30 <= len(f.strip()) <= 1500]
    if not frases_validas:
        return texto[:500], idioma
    if len(frases_validas) <= n_frases:
        return " ".join(frases_validas), idioma

    stop = set(stopwords.words(idioma))
    palavras = [w.lower() for w in nltk.word_tokenize(texto) if w.isalpha() and w.lower() not in stop]
    freq = FreqDist(palavras)

    pontuadas = []
    for idx, frase in enumerate(frases_validas):
        toks = [w.lower() for w in nltk.word_tokenize(frase) if w.isalpha() and w.lower() not in stop]
        if not toks:
            continue
        score = sum(freq[t] for t in toks) / math.sqrt(len(toks))
        if idx < 3:
            score *= 1.1
        pontuadas.append((idx, score))

    if not pontuadas:
        return " ".join(frases_validas[:n_frases]), idioma

    pontuadas.sort(key=lambda x: x[1], reverse=True)
    escolhidas = sorted(idx for idx, _ in pontuadas[:n_frases])
    resumo = " ".join(frases_validas[i] for i in escolhidas)
    return resumo, idioma


def link_email(msg_id, thread_id=None):
    """Link do Gmail web que abre o e-mail completo para leitura."""
    ref = thread_id or msg_id
    return f"https://mail.google.com/mail/u/0/#inbox/{ref}"


# ============================================================
# Gmail + Resumo
# ============================================================

def resumir_emails():
    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.modify"]

    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if os.path.exists("token.json"):
                try:
                    os.remove("token.json")
                except OSError:
                    pass
            if not os.path.exists("credentials.json"):
                console.print("[red]ERRO: credentials.json não encontrado.[/red]")
                console.print("Baixe no Google Cloud Console (OAuth Client > Desktop) e salve como credentials.json")
                return
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            try:
                creds = flow.run_local_server(port=0, prompt="consent", authorization_prompt_message="Abra {url} no navegador e clique em Permitir.", timeout_seconds=120)
            except AccessDeniedError as e:
                console.print("\n[red]❌ Acesso negado no Google (access_denied).[/red]")
                console.print("   → Na tela de consentimento, clique em 'Permitir' / 'Continuar' e autorize os escopos do Gmail.")
                console.print("   → Se aparecer 'aplicativo não verificado', clique em 'Avançado' > 'Ir para o projeto (não seguro)'.")
                console.print("   → Depois rode novamente a opção 1.")
                console.print(f"   Detalhe: {e}")
                return
            except KeyboardInterrupt:
                console.print("\nOperação cancelada.")
                return
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("gmail", "v1", credentials=creds)

        def listar_nao_lidos(consulta, max_paginas=20):
            lista = []
            params = {"userId": "me", "labelIds": ["UNREAD"], "q": consulta}
            for _ in range(max_paginas):
                results = service.users().messages().list(**params).execute()
                lista += results.get("messages") or []
                token = results.get("nextPageToken")
                if not token:
                    break
                params["pageToken"] = token
            return lista

        # Procura o dia mais recente com não-lidos
        data_alvo = None
        lista = []
        hoje = datetime.now(timezone.utc).date()
        busca = []
        for dias_atras in range(0, 30):
            dia = hoje - timedelta(days=dias_atras)
            dia_str = dia.strftime("%Y/%m/%d")
            dia_anterior = (dia - timedelta(days=1)).strftime("%Y/%m/%d")
            dia_seguinte = (dia + timedelta(days=1)).strftime("%Y/%m/%d")
            consulta = f"after:{dia_anterior} before:{dia_seguinte}"
            achados = listar_nao_lidos(consulta)
            busca.append((dia_str, len(achados)))
            if achados:
                data_alvo = dia_str
                lista = achados
                break

        table = Table(title="Busca do dia mais recente com não-lidos", show_header=True)
        table.add_column("Data")
        table.add_column("Não-lidos", justify="right")
        for dia_str, qtd in busca:
            style = "bold green" if qtd else None
            table.add_row(dia_str, str(qtd), style=style)
            if dia_str == data_alvo:
                break
        console.print(table)

        if not data_alvo or not lista:
            console.print("\n[yellow]Nenhum email não-lido encontrado nos últimos 30 dias.[/yellow]")
            console.print("Terminou")
            return

        console.print(f"\n[bold]Dia escolhido: {data_alvo} com {len(lista)} emails[/bold]")

        with open("lista_emails.json", "w", encoding="utf-8") as arquivo:
            json.dump(lista, arquivo)

        console.print(f"\n[cyan]Etapa 2... ({len(lista)} email(s) de {data_alvo} para resumir)[/cyan]")

        lista_negra = carregar_lista_negra()
        resumos = []
        ignorados = []

        for mensagem in lista:
            msg_id = mensagem.get("id")
            msg = service.users().messages().get(userId="me", id=msg_id).execute()
            payload = msg.get("payload", {})

            remetente = obter_header(payload, "From")
            assunto = obter_header(payload, "Subject")
            data = obter_header(payload, "Date")

            # Lista negra: ignora o resumo, mas marca como lido
            if esta_bloqueado(remetente, lista_negra):
                console.print(f"[yellow]⚠ ignorado (lista negra): {escape(remetente)}[/yellow]")
                service.users().messages().modify(
                    userId="me",
                    id=msg_id,
                    body={"removeLabelIds": ["UNREAD"]},
                ).execute()
                ignorados.append({"id": msg_id, "de": remetente, "assunto": assunto, "data": data})
                continue

            texto = extrair_texto_email(msg)
            resumo, idioma = gerar_resumo_extrativo(texto, n_frases=N_FRASES_RESUMO)
            link = link_email(msg_id, msg.get("threadId"))

            # Panel com link clicável (OSC 8 via Text)
            linhas = [
                f"[bold]{escape(assunto) or '(sem assunto)'}[/bold]",
                f"[dim]{escape(data)}[/dim]",
                "",
                f"[bold]Resumo ({idioma}):[/bold] {escape(resumo)}",
                "",
            ]
            titulo = f"{remetente}"
            painel = Panel("\n".join(linhas).rstrip(), title=escape(titulo)[:80], border_style="blue")
            console.print(painel)
            link_txt = Text("▶ Ler email completo", style=f"link {link}")
            # Estilo extra via markup no Text final
            link_txt.style = f"underline cyan link {link}"
            console.print(link_txt)

            # Pergunta interativa, só para remetente novo (não está na lista negra)
            resposta = input(f"Adicionar {extrair_email(remetente)} à lista negra? [s/N]: ").strip().lower()
            if resposta == "s":
                lista_negra.append(extrair_email(remetente))
                salvar_lista_negra(lista_negra)
                console.print(f"[green]✓ {escape(extrair_email(remetente))} adicionado(a) à lista negra.[/green]")
                service.users().messages().modify(
                    userId="me",
                    id=msg_id,
                    body={"removeLabelIds": ["UNREAD"]},
                ).execute()
                ignorados.append({"id": msg_id, "de": remetente, "assunto": assunto, "data": data,
                                  "motivo": "adicionado durante o resumo"})
                continue

            resumos.append({
                "id": msg_id,
                "de": remetente,
                "assunto": assunto,
                "data": data,
                "resumo": resumo,
                "idioma": idioma,
                "link_email": link,
            })

            service.users().messages().modify(
                userId="me",
                id=msg_id,
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()

        nome_arquivo = f"resumo_dia_{datetime.now().strftime('%Y-%m-%d')}.json"
        payload_json = {
            "dia": data_alvo,
            "resumidos": resumos,
            "ignorados": ignorados,
        }
        with open(nome_arquivo, "w", encoding="utf-8") as f:
            json.dump(payload_json, f, ensure_ascii=False, indent=2)

        console.print(
            f"\n[bold]Resumo: {len(resumos)} resumido(s) · {len(ignorados)} ignorado(s) (lista negra) · JSON salvo em {nome_arquivo}[/bold]"
        )

        console.print("[bold]Terminou[/bold]")

    except HttpError as error:
        console.print(f"[red]An error occurred: {error}[/red]")


opcoes = [("0 - Sair",), ("1 - Resumidor de Emails", resumir_emails)]

for opcao in opcoes:
    print(opcao[0])


while True:
    i = input()
    if i == "0":
        break
    opcao = int(i)
    opcoes[opcao][1]()
