"""GAIA - Gestão e Assistência com Inteligência Artificial.
Entrypoint fino: só wiring (banner, scheduler, menu). Sem regra de negócio.

Monitor em tempo real: tela principal sempre com CPU+RAM+GAIA (Live a cada 1s,
amostragem em background a cada 2s em `monitor_historico.jsonl`, log por rotina
em `monitor_rotinas.jsonl`). Ver `gaia/core/monitor.py` e `gaia/ui/monitor_render.py`.

Compat: re-exporta símbolos históricos de main.py para testes antigos.
"""

import pyfiglet
from rich.panel import Panel
from googleapiclient.errors import HttpError

from gaia.config import MONITOR_INTERVALO_FUNDO, MONITOR_JANELA_SPARKLINE, N_FRASES_RESUMO
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


def criar_monitor():
    from gaia.core.monitor import Monitor, coletar_metricas
    from gaia.core.storage import anexar_monitor_amostra

    return Monitor(
        coleta_fn=lambda: coletar_metricas(),
        salvar_fn=lambda amostra: anexar_monitor_amostra(amostra),
        intervalo=MONITOR_INTERVALO_FUNDO,
    )


def resumir_emails():
    from gaia.core.monitor import medir_rotina

    @medir_rotina("resumir_emails")
    def _chamar():
        return _resumir_emails_impl(console=get_console())

    return _chamar()


def criar_tarefa_scheduler():
    from gaia.core.monitor import medir_rotina

    @medir_rotina("resumir_emails")
    def tarefa():
        return _resumir_emails_impl(
            console=get_console(),
            prompter=lambda email: False,
            pager_input=lambda prompt="": "",
            perguntar_lista_negra=False,
        )

    return tarefa


def tecla_para_acao(tecla):
    """Mapeia uma tecla única para ação do menu (sem Enter).

    - "1" → executar rotina resumidor
    - "2" → executar histórico
    - "0"/"q"/"Q"/Ctrl+C → sair
    - Enter/"" /outras → ignorar (None), sem erro.
    """
    if tecla in ("0", "q", "Q", "\x03"):
        return "sair"
    if tecla == "1":
        return "executar_1"
    if tecla == "2":
        return "executar_2"
    return None


def ler_tecla(timeout=1.0, stdin=None):
    """Lê 1 tecla em modo cru (sem Enter, sem echo).

    Retorna o caractere, "" em EOF, ou None em timeout (para o Live redesenhar).
    Se termios/select indisponíveis, retorna None (fallback não bloqueante).
    """
    if stdin is None:
        import sys as _sys

        stdin = _sys.stdin
    try:
        import os
        import select
        import termios
    except ImportError:
        return None
    try:
        fd = stdin.fileno()
    except Exception:
        return None
    try:
        antigo = termios.tcgetattr(fd)
    except Exception:
        return None
    try:
        novo = termios.tcgetattr(fd)
        novo[3] = novo[3] & ~(termios.ICANON | termios.ECHO)
        termios.tcsetattr(fd, termios.TCSANOW, novo)
        prontos, _, _ = select.select([stdin], [], [], timeout)
        if not prontos:
            return None
        dados = os.read(fd, 1)
        if not dados:
            return ""
        try:
            return dados.decode("utf-8", errors="ignore")
        except Exception:
            return ""
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSANOW, antigo)
        except Exception:
            pass


def executar_rotina(funcao, titulo, console=None):
    if console is None:
        console = get_console()
    try:
        return funcao()
    except KeyboardInterrupt:
        console.print("\nOperação cancelada.")
    except Exception as exc:
        exibir_traceback(console, exc, contexto=titulo)


def mostrar_banner(console=None, amostra=None, historico_cpu=None, historico_ram=None):
    if console is None:
        console = get_console()
    ascii_arte = pyfiglet.figlet_format("GAIA", font="banner")
    console.print(Panel(ascii_arte, title="GAIA", border_style="blue"))
    if amostra is not None:
        from gaia.ui.monitor_render import render_monitor

        console.print(render_monitor(amostra, historico_cpu, historico_ram))
    console.print("Digite a opção para rodar a rotina descrita:")
    if tem_resumo_pendente():
        console.print(Panel("Resumo automático pronto! Opção 1 → Abrir último para ver.", title="Resumo automático", border_style="yellow"))


def historico():
    from gaia.routines.historico import mostrar_historico

    return mostrar_historico(console=get_console())


def construir_menu():
    menu = Menu()
    menu.registrar("0", "Sair", None)
    menu.registrar("1", "Resumidor de Emails", resumir_emails)
    menu.registrar("2", "Histórico", historico)
    return menu


def main():
    console = get_console()

    # A1: scheduler em background (daemon) — não bloqueia o menu interativo
    scheduler = Scheduler(tarefa=criar_tarefa_scheduler(), hora=6, minuto=0)
    scheduler.start()

    # Monitor em tempo real: amostragem em background a cada 2s (JSONL)
    monitor = criar_monitor()
    monitor.iniciar()

    menu = construir_menu()

    try:
        loop_menu_com_monitor(console, menu, monitor)
    finally:
        monitor.parar()
        scheduler.stop()


def loop_menu_com_monitor(console, menu, monitor, intervalo_tela=None, entrada=None, pausa=None, ler_tecla_fn=None):
    """Tela principal com monitor dinâmico (Live) na tela principal.

    - `entrada`: callable injetável para testes (retorna próxima escolha com Enter).
      Em produção (None), usa Live contínuo + tecla única (sem Enter, estilo htop).
    - `ler_tecla_fn`: injetável para testes (timeout → char ou None).
    - Monitor aparece sempre na tela principal; ao executar rotina, o Live
      pausa e depois retoma ao voltar.
    """
    import time

    from rich.console import Group

    from gaia.config import MONITOR_INTERVALO_TELA
    from gaia.ui.monitor_render import render_monitor

    janela = MONITOR_JANELA_SPARKLINE
    if intervalo_tela is None:
        intervalo_tela = MONITOR_INTERVALO_TELA

    def render_tela():
        amostra = monitor.ultima_amostra() if monitor is not None else None
        h_cpu = monitor.historico_cpu(janela) if monitor is not None else []
        h_ram = monitor.historico_ram(janela) if monitor is not None else []
        ascii_arte = pyfiglet.figlet_format("GAIA", font="banner")
        partes = [Panel(ascii_arte, title="GAIA", border_style="blue")]
        if amostra is not None or h_cpu:
            partes.append(render_monitor(amostra, h_cpu, h_ram))
        linhas_menu = "\n".join(f"{tecla} - {titulo}" for tecla, (titulo, _) in menu.itens())
        from rich.text import Text

        partes.append(Text("Pressione a tecla: 1=Resumidor  2=Histórico  0/q=Sair (sem Enter)\n" + linhas_menu))
        if tem_resumo_pendente():
            partes.append(Panel("Resumo automático pronto! Opção 1 → Abrir último para ver.", title="Resumo automático", border_style="yellow"))
        return Group(*partes)

    # Caminho de teste: entrada injetada, sem Live (determinístico)
    if entrada is not None:
        while True:
            console.clear()
            resto = None
            if pausa is not None:
                resto = pausa
            amostra = monitor.ultima_amostra() if monitor is not None else None
            h_cpu = monitor.historico_cpu(janela) if monitor is not None else []
            h_ram = monitor.historico_ram(janela) if monitor is not None else []
            mostrar_banner(console, amostra=amostra, historico_cpu=h_cpu, historico_ram=h_ram)
            for tecla, (titulo, _) in menu.itens():
                console.print(f"{tecla} - {titulo}")
            console.print("")
            try:
                escolha = entrada().strip()
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
            if resto is not None:
                try:
                    resto("Pressione Enter para voltar ao menu... ")
                except EOFError:
                    break
            else:
                try:
                    input("Pressione Enter para voltar ao menu... ")
                except EOFError:
                    break
        return

    # Caminho real: Live contínuo (estilo htop) + tecla única.
    # input() de linha enquanto o Live redesenha apaga a digitação; tecla
    # única em modo cru não tem linha para apagar e atualiza sem parar.
    from rich.live import Live

    if ler_tecla_fn is None:
        ler_tecla_fn = ler_tecla

    while True:
        with Live(render_tela(), console=console, transient=False, refresh_per_second=2) as live:
            while True:
                live.update(render_tela())
                try:
                    tecla = ler_tecla_fn(intervalo_tela)
                except (EOFError, KeyboardInterrupt):
                    tecla = ""
                if tecla is None:
                    continue
                if tecla == "":
                    return
                acao = tecla_para_acao(tecla)
                if acao == "sair":
                    return
                if acao in ("executar_1", "executar_2"):
                    tecla = "1" if acao == "executar_1" else "2"
                    try:
                        funcao = menu.obter(tecla)
                    except KeyError:
                        continue
                    titulo = dict(menu.itens()).get(tecla, (tecla,))[0]
                    live.stop()
                    exibir_cabecalho_rotina(console, titulo)
                    executar_rotina(funcao, titulo, console=console)
                    try:
                        if pausa is not None:
                            pausa("Pressione Enter para voltar ao menu... ")
                        else:
                            input("Pressione Enter para voltar ao menu... ")
                    except EOFError:
                        return
                    live.start()
                    time.sleep(0.05)
                # outras teclas (incl. Enter) são ignoradas, sem erro


if __name__ == "__main__":
    main()
