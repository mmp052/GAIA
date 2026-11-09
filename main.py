"""GAIA - Gestão e Assistência com Inteligência Artificial.
Entrypoint fino: só wiring (banner, scheduler, menu). Sem regra de negócio.

Compat: re-exporta símbolos históricos de main.py para testes antigos.
"""

import pyfiglet
from rich.panel import Panel
from googleapiclient.errors import HttpError

from gaia.config import N_FRASES_RESUMO
from gaia.core.blacklist import carregar_lista_negra, esta_bloqueado, extrair_email, salvar_lista_negra
from gaia.core.email_extract import (
    _coletar_textos,
    decodificar_base64url,
    extrair_texto_email,
    limpar_html,
    limpar_texto,
    link_email,
    obter_header,
)
from gaia.core.nlp import _garantir_recursos_nltk, detectar_idioma, gerar_resumo_extrativo
from gaia.ui.console import get_console
from gaia.ui.erros import exibir_traceback
from gaia.ui.menu import Menu
from gaia.ui.screens import exibir_cabecalho_rotina
from gaia.scheduler import Scheduler
from gaia.routines.resumidor_emails import resumir_emails as _resumir_emails_impl
from gaia.routines.resumidor_emails import tem_resumo_pendente

__all__ = [
    "N_FRASES_RESUMO",
    "carregar_lista_negra",
    "salvar_lista_negra",
    "extrair_email",
    "esta_bloqueado",
    "obter_header",
    "decodificar_base64url",
    "_coletar_textos",
    "limpar_html",
    "extrair_texto_email",
    "limpar_texto",
    "detectar_idioma",
    "gerar_resumo_extrativo",
    "link_email",
    "_garantir_recursos_nltk",
    "resumir_emails",
]


def resumir_emails():
    return _resumir_emails_impl(console=get_console())


def criar_tarefa_scheduler():
    def tarefa():
        return _resumir_emails_impl(
            console=get_console(),
            prompter=lambda email: False,
            pager_input=lambda prompt="": "",
            perguntar_lista_negra=False,
        )

    return tarefa


def executar_rotina(funcao, titulo, console=None):
    if console is None:
        console = get_console()
    try:
        return funcao()
    except KeyboardInterrupt:
        console.print("\nOperação cancelada.")
    except Exception as exc:
        exibir_traceback(console, exc, contexto=titulo)


def mostrar_banner(console=None):
    if console is None:
        console = get_console()
    ascii_arte = pyfiglet.figlet_format("GAIA", font="banner")
    console.print(Panel(ascii_arte, title="GAIA", border_style="blue"))
    console.print("Digite a opção para rodar a rotina descrita:")
    if tem_resumo_pendente():
        console.print(Panel("Resumo automático pronto! Opção 1 → Abrir último para ver.", title="Resumo automático", border_style="yellow"))


def construir_menu():
    menu = Menu()
    menu.registrar("0", "Sair", None)
    menu.registrar("1", "Resumidor de Emails", resumir_emails)
    return menu


def main():
    console = get_console()

    # A1: scheduler em background (daemon) — não bloqueia o menu interativo
    scheduler = Scheduler(tarefa=criar_tarefa_scheduler(), hora=6, minuto=0)
    scheduler.start()

    menu = construir_menu()

    try:
        while True:
            console.clear()
            mostrar_banner(console)
            for tecla, (titulo, _) in menu.itens():
                console.print(f"{tecla} - {titulo}")
            console.print("")
            try:
                escolha = input().strip()
            except EOFError:
                break
            if escolha == "0":
                break
            try:
                funcao = menu.obter(escolha)
            except KeyError:
                console.print("Opção inválida. Tente novamente.")
                continue
            if funcao is None:
                break
            titulo = dict(menu.itens()).get(escolha, (escolha,))[0]
            exibir_cabecalho_rotina(console, titulo)
            executar_rotina(funcao, titulo, console=console)
            try:
                input("Pressione Enter para voltar ao menu... ")
            except EOFError:
                break
    finally:
        scheduler.stop()


if __name__ == "__main__":
    main()
