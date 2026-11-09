import threading
from datetime import datetime, timezone

from gaia.config import N_FRASES_RESUMO
from gaia.core.blacklist import carregar_lista_negra, carregar_lista_permitida, esta_bloqueado, esta_permitido, extrair_email, salvar_lista_negra, salvar_lista_permitida
from gaia.core.email_extract import extrair_texto_email, link_email, obter_header
from gaia.core.gmail_auth import obter_credenciais
from gaia.core.gmail_client import buscar_dia_mais_recente, buscar_ultimas_24h, marcar_como_lida, obter_mensagem
from gaia.core.nlp import gerar_resumo_extrativo
from gaia.core.storage import carregar_ultimo_resumo, salvar_lista_emails, salvar_resumo_dia
from gaia.ui.console import get_console
from gaia.ui.progress import criar_progress
from gaia.ui.render import render_painel_resumo, render_tabela_busca, texto_link_email
from gaia.ui.screens import exibir_paginado

_execucao_lock = threading.Lock()
_resumo_pendente = threading.Event()


def marcar_resumo_pendente():
    _resumo_pendente.set()


def limpar_resumo_pendente():
    _resumo_pendente.clear()


def tem_resumo_pendente():
    return _resumo_pendente.is_set()


def processar_mensagem(msg_id, msg, lista_negra, prompter=None, resumo_fn=None, thread_id=None):
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

    # A pergunta da lista negra NÃO acontece aqui: resumir_email() resume todos
    # primeiro, salva e só depois pergunta (na fase de resultados) com o resumo já visto.
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


def resumir_emails(service=None, prompter=None, console=None, logger=None, pager_input=None, por_pagina=5, perguntar_lista_negra=True, escolher_opcao=None):
    if console is None:
        console = get_console()

    if not _execucao_lock.acquire(blocking=False):
        console.print("[yellow]Já há uma execução em andamento, ignorando nova solicitação.[/yellow]")
        return {"dia": None, "resumidos": [], "ignorados": [], "falhas": []}
    try:
        return _resumir_emails_impl(
            service=service,
            prompter=prompter,
            console=console,
            logger=logger,
            pager_input=pager_input,
            por_pagina=por_pagina,
            perguntar_lista_negra=perguntar_lista_negra,
            escolher_opcao=escolher_opcao,
        )
    finally:
        _execucao_lock.release()


def _resumir_emails_impl(service=None, prompter=None, console=None, logger=None, pager_input=None, por_pagina=5, perguntar_lista_negra=True, escolher_opcao=None):
    if console is None:
        console = get_console()

    if perguntar_lista_negra:
        ultimo = carregar_ultimo_resumo()
        if ultimo is not None and ultimo.get("resumidos"):
            if escolher_opcao is None:

                def escolher_opcao():
                    resposta = input(f"\nExiste resumo ({ultimo['dia']}, {len(ultimo['resumidos'])} email(s), {ultimo['arquivo']}). [1] Abrir último [2] Buscar novo: ").strip().lower()
                    return "abrir" if resposta in ("1", "abrir", "a") else "novo"

            opcao = str(escolher_opcao()).strip().lower()
            if opcao in ("abrir", "1", "a"):
                blocos = []
                for item in ultimo["resumidos"]:
                    painel = render_painel_resumo(item.get("de", ""), item.get("assunto", ""), item.get("data", ""), item.get("resumo", ""), item.get("idioma", ""))
                    blocos.append((painel, texto_link_email(item.get("link_email", ""))))
                console.print(f"\n[bold]Último resumo: {ultimo['dia']} · {len(ultimo['resumidos'])} email(s) · {ultimo['arquivo']}[/bold]")
                entrada = pager_input if pager_input is not None else input
                for idx_abrir, bloco_abrir in enumerate(blocos):
                    console.clear()
                    if isinstance(bloco_abrir, (list, tuple)):
                        for parte in bloco_abrir:
                            console.print(parte)
                    else:
                        console.print(bloco_abrir)
                    if idx_abrir < len(blocos) - 1:
                        entrada("Pressione Enter para próximo...")
                console.print("[bold]Terminou[/bold]")
                limpar_resumo_pendente()
                return {"dia": ultimo["dia"], "resumidos": ultimo["resumidos"], "ignorados": ultimo["ignorados"], "falhas": [], "arquivo": ultimo["arquivo"]}

    if service is None:
        # import tardio para não quebrar testes sem google-api ainda
        from googleapiclient.discovery import build

        creds = obter_credenciais(console=console)
        if creds is None:
            return {"dia": None, "resumidos": [], "ignorados": [], "falhas": []}
        service = build("gmail", "v1", credentials=creds)

    hoje = datetime.now(timezone.utc).date()

    if prompter is None:

        def prompter(email):
            resposta = input(f"Adicionar {email} à lista negra? [s/N]: ").strip().lower()
            return resposta == "s"

    resumos = []
    ignorados = []
    blocos = []

    with criar_progress(console) as progress:
        if perguntar_lista_negra:
            task_busca = progress.add_task("Buscando dia com não-lidos...", total=30)

            def _cb_busca(dia_str, qtd, atual, total):
                progress.update(task_busca, advance=1, description=f"Buscando... {dia_str} ({qtd} não-lidos) [{atual}/{total}]")

            data_alvo, lista, busca = buscar_dia_mais_recente(service, hoje, on_progress=_cb_busca)
        else:
            task_busca = progress.add_task("Buscando últimas 24h...", total=1)

            def _cb_busca24(dia_str, qtd, atual, total):
                progress.update(task_busca, advance=1, description=f"Buscando últimas 24h... ({qtd} não-lidos)")

            agora = datetime.now(timezone.utc)
            data_alvo, lista, busca = buscar_ultimas_24h(service, agora, on_progress=_cb_busca24)

    table = render_tabela_busca(busca, data_alvo)
    console.print(table)

    if not data_alvo or not lista:
        if perguntar_lista_negra:
            console.print("\n[yellow]Nenhum email não-lido encontrado nos últimos 30 dias.[/yellow]")
        else:
            console.print("\n[yellow]Nenhum email não-lido nas últimas 24 horas.[/yellow]")
        console.print("Terminou")
        return {"dia": None, "resumidos": [], "ignorados": [], "falhas": []}

    console.print(f"\n[bold]Dia escolhido: {data_alvo} com {len(lista)} emails[/bold]")
    salvar_lista_emails(lista)
    console.print(f"\n[cyan]Etapa 2... ({len(lista)} email(s) de {data_alvo} para resumir)[/cyan]")

    lista_negra = carregar_lista_negra()
    lista_permitida = carregar_lista_permitida()

    with criar_progress(console) as progress:
        task_emails = progress.add_task("Processando emails", total=len(lista))

        for idx, mensagem in enumerate(lista, 1):
            msg_id = mensagem.get("id")
            progress.update(task_emails, description=f"Email {idx}/{len(lista)} [{msg_id}] — buscando")
            msg = obter_mensagem(service, msg_id)
            progress.update(task_emails, description=f"Email {idx}/{len(lista)} [{msg_id}] — resumindo")
            resultado = processar_mensagem(msg_id, msg, lista_negra)
            progress.update(task_emails, description=f"Email {idx}/{len(lista)} [{msg_id}] — marcando lida")

            if resultado.get("ignorado"):
                if resultado.get("motivo") == "lista negra":
                    console.print(f"[yellow]⚠ ignorado (lista negra): {resultado['de']}[/yellow]")
                    ignorados.append({"id": msg_id, "de": resultado["de"], "assunto": resultado["assunto"], "data": resultado["data"]})
            else:
                painel = render_painel_resumo(resultado["de"], resultado["assunto"], resultado["data"], resultado["resumo"], resultado["idioma"])
                blocos.append((painel, texto_link_email(resultado["link_email"])))
                resumos.append(
                    {
                        "id": msg_id,
                        "de": resultado["de"],
                        "assunto": resultado["assunto"],
                        "data": resultado["data"],
                        "resumo": resultado["resumo"],
                        "idioma": resultado["idioma"],
                        "link_email": resultado["link_email"],
                    }
                )
            marcar_como_lida(service, msg_id)
            progress.update(task_emails, advance=1)

    # Salva com TODOS os resumidos antes de mostrar/perguntar.
    nome_arquivo = salvar_resumo_dia(data_alvo, resumos, ignorados)
    console.print(f"\n[bold]Resumo: {len(resumos)} resumido(s) · {len(ignorados)} ignorado(s) (lista negra) · JSON salvo em {nome_arquivo}[/bold]")

    # Fase de resultados interativa: um email por vez com clear + pergunta imediata.
    # Scheduler (não-interativo) despeja tudo de uma vez, sem clear/pergunta.
    if perguntar_lista_negra:
        entrada = pager_input if pager_input is not None else input
        itens = list(zip(resumos, blocos))
        bloqueados_agora = set()
        for idx, (item, bloco) in enumerate(itens):
            console.clear()
            if isinstance(bloco, (list, tuple)):
                for parte in bloco:
                    console.print(parte)
            else:
                console.print(bloco)
            email = extrair_email(item["de"])
            eh_novo = not esta_bloqueado(item["de"], lista_negra) and not esta_permitido(item["de"], lista_permitida)
            if eh_novo:
                if prompter(email):
                    lista_negra.append(email)
                    salvar_lista_negra(lista_negra)
                    console.print(f"[green]✓ {email} adicionado(a) à lista negra.[/green]")
                    bloqueados_agora.add(email)
                else:
                    lista_permitida.append(email)
                    salvar_lista_permitida(lista_permitida)
                    console.print(f"[green]✓ {email} mantido(a). Não perguntaremos de novo.[/green]")
            elif idx < len(itens) - 1:
                entrada("Pressione Enter para próximo...")
        if bloqueados_agora:
            movidos = [r for r in resumos if extrair_email(r["de"]) in bloqueados_agora]
            resumos = [r for r in resumos if extrair_email(r["de"]) not in bloqueados_agora]
            for r in movidos:
                ignorados.append({"id": r["id"], "de": r["de"], "assunto": r["assunto"], "data": r["data"], "motivo": "adicionado durante o resumo"})
            nome_arquivo = salvar_resumo_dia(data_alvo, resumos, ignorados)
            console.print(f"\n[bold]Resumo final: {len(resumos)} resumido(s) · {len(ignorados)} ignorado(s) · JSON salvo em {nome_arquivo}[/bold]")
    else:
        if blocos:
            exibir_paginado(console, blocos, por_pagina=por_pagina, entrada=pager_input)

    console.print("[bold]Terminou[/bold]")
    if perguntar_lista_negra:
        limpar_resumo_pendente()
    elif data_alvo is not None:
        marcar_resumo_pendente()
    return {"dia": data_alvo, "resumidos": resumos, "ignorados": ignorados, "falhas": [], "arquivo": nome_arquivo}
