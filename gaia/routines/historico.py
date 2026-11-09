"""Rotina Histórico — Hoje e ontem (tela única, sem exportar).

Reutiliza `gaia/core/historico` + `gaia/ui/historico_render`.
Não importa `input` direto (recebe `pager_input` injetável, ignorado — sem paginar).
"""

from gaia.core.historico import obter_historico_completo
from gaia.ui.console import get_console
from gaia.ui.historico_render import render_grafico_grande, render_resumo_historico, render_tabela_ranking


def mostrar_historico(console=None, pager_input=None, historico_fn=None):
    if console is None:
        console = get_console()
    obter = historico_fn if historico_fn is not None else obter_historico_completo
    dados = obter()
    por_hora = dados.get("por_hora") or []
    serie_cpu = [b.get("cpu_pico", 0.0) for b in por_hora]
    serie_ram = [b.get("ram_pico", 0.0) for b in por_hora]
    rotulos = [b.get("hora", "") for b in por_hora]

    console.clear()
    console.print(render_resumo_historico(dados.get("resumo") or {}))
    console.print(render_grafico_grande(serie_cpu, titulo="CPU (%) — pico por hora", rotulos=rotulos, largura=48, altura=6))
    console.print(render_grafico_grande(serie_ram, titulo="RAM (%) — pico por hora", rotulos=rotulos, largura=48, altura=6))
    console.print(render_tabela_ranking(dados.get("ranking") or []))
    console.print("[bold]Terminou[/bold]")
    return {"resumo": dados.get("resumo") or {}, "ranking": dados.get("ranking") or [], "por_hora": por_hora}
