"""Rotina Resumidor — busca e-mails não lidos das últimas 24h.

A interface PyWebview é a única camada visual: este módulo não imprime nem
solicita entrada do usuário. A progressão é comunicada por ``on_progress`` e
os resultados são devolvidos como dados estruturados para a tela.
"""

import threading
from datetime import datetime, timezone

from gaia.config import N_FRASES_RESUMO
from gaia.core.blacklist import carregar_lista_negra, esta_bloqueado
from gaia.core.email_extract import extrair_texto_email, link_email, obter_header
from gaia.core.gmail_auth import obter_credenciais
from gaia.core.gmail_client import buscar_ultimas_24h, marcar_como_lida, obter_mensagem
from gaia.core.nlp import gerar_resumo_extrativo
from gaia.core.storage import salvar_lista_emails, salvar_resumo_dia

_execucao_lock = threading.Lock()
_resumo_pendente = threading.Event()


def marcar_resumo_pendente():
    _resumo_pendente.set()


def limpar_resumo_pendente():
    _resumo_pendente.clear()


def tem_resumo_pendente():
    return _resumo_pendente.is_set()


def _avisar(on_progress, msg):
    if on_progress is None:
        return
    try:
        on_progress(str(msg))
    except Exception:
        # Progresso não pode derrubar a rotina.
        pass


def processar_mensagem(msg_id, msg, lista_negra, resumo_fn=None, thread_id=None):
    """Resume uma mensagem ou a marca como ignorada por lista negra."""
    if resumo_fn is None:
        resumo_fn = gerar_resumo_extrativo
    payload = msg.get("payload", {})
    remetente = obter_header(payload, "From")
    assunto = obter_header(payload, "Subject")
    data = obter_header(payload, "Date")

    if esta_bloqueado(remetente, lista_negra):
        return {
            "ignorado": True,
            "id": msg_id,
            "de": remetente,
            "assunto": assunto,
            "data": data,
            "motivo": "lista negra",
        }

    texto = extrair_texto_email(msg)
    resumo, idioma = resumo_fn(texto, n_frases=N_FRASES_RESUMO)
    link = link_email(msg_id, thread_id or msg.get("threadId"))

    return {
        "ignorado": False,
        "id": msg_id,
        "de": remetente,
        "assunto": assunto,
        "data": data,
        "resumo": resumo,
        "idioma": idioma,
        "link_email": link,
    }


def resumir_emails(service=None, on_progress=None, logger=None, agora=None):
    """Executa a rotina protegida contra execuções concorrentes."""
    if not _execucao_lock.acquire(blocking=False):
        _avisar(on_progress, "Já há uma execução em andamento.")
        return {"dia": None, "resumidos": [], "ignorados": [], "falhas": []}
    try:
        return _resumir_emails_impl(service=service, on_progress=on_progress, logger=logger, agora=agora)
    finally:
        _execucao_lock.release()


def _resumir_emails_impl(service=None, on_progress=None, logger=None, agora=None):
    if service is None:
        from googleapiclient.discovery import build

        creds = obter_credenciais()
        if creds is None:
            _avisar(on_progress, "Não foi possível autorizar o Gmail.")
            return {"dia": None, "resumidos": [], "ignorados": [], "falhas": []}
        service = build("gmail", "v1", credentials=creds)

    agora = agora or datetime.now(timezone.utc)
    _avisar(on_progress, "Buscando últimas 24h...")

    def _progresso_busca(dia_str, qtd, atual, total):
        _avisar(on_progress, f"Buscando últimas 24h... ({qtd} não-lidos)")

    data_alvo, lista, _busca = buscar_ultimas_24h(service, agora, on_progress=_progresso_busca)

    if not data_alvo or not lista:
        _avisar(on_progress, "Nenhum email não-lido nas últimas 24 horas.")
        return {"dia": None, "resumidos": [], "ignorados": [], "falhas": []}

    _avisar(on_progress, f"Dia escolhido: {data_alvo} — {len(lista)} email(s)")
    salvar_lista_emails(lista)

    lista_negra = carregar_lista_negra()
    resumos = []
    ignorados = []

    for idx, mensagem in enumerate(lista, 1):
        msg_id = mensagem.get("id")
        _avisar(on_progress, f"Email {idx}/{len(lista)} — buscando")
        msg = obter_mensagem(service, msg_id)

        _avisar(on_progress, f"Email {idx}/{len(lista)} — resumindo")
        resultado = processar_mensagem(msg_id, msg, lista_negra)

        _avisar(on_progress, f"Email {idx}/{len(lista)} — marcando lida")
        if resultado.get("ignorado"):
            if resultado.get("motivo") == "lista negra":
                ignorados.append({
                    "id": msg_id,
                    "de": resultado["de"],
                    "assunto": resultado["assunto"],
                    "data": resultado["data"],
                })
        else:
            resumos.append({
                "id": msg_id,
                "de": resultado["de"],
                "assunto": resultado["assunto"],
                "data": resultado["data"],
                "resumo": resultado["resumo"],
                "idioma": resultado["idioma"],
                "link_email": resultado["link_email"],
            })
        marcar_como_lida(service, msg_id)

    nome_arquivo = salvar_resumo_dia(data_alvo, resumos, ignorados)
    _avisar(on_progress, f"Resumo: {len(resumos)} resumido(s) · {len(ignorados)} ignorado(s)")
    if data_alvo is not None:
        marcar_resumo_pendente()

    return {
        "dia": data_alvo,
        "resumidos": resumos,
        "ignorados": ignorados,
        "falhas": [],
        "arquivo": nome_arquivo,
    }
