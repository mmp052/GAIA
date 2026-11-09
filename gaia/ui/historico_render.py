"""Renderização do módulo de histórico (Hoje e ontem)."""

from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def render_resumo_historico(resumo):
    """Painel com pico/média de CPU e RAM + total de amostras."""
    resumo = resumo or {}
    linhas = [
        f"CPU pico {float(resumo.get('cpu_pico', 0.0)):.1f}% | média {float(resumo.get('cpu_media', 0.0)):.1f}%",
        f"RAM pico {float(resumo.get('ram_pico', 0.0)):.1f}% | média {float(resumo.get('ram_media', 0.0)):.1f}%",
        f"Amostras: {int(resumo.get('total', 0))}",
    ]
    return Panel(Text("\n".join(linhas)), title="Histórico — Hoje e ontem", border_style="blue")


def render_grafico_grande(valores, titulo, rotulos=None, largura=60, altura=8):
    """Gráfico ASCII grande: colunas por valor (0-100%), com eixos X/Y.

    - Eixo Y: rótulos 100%/50%/0% à esquerda (altura da barra → %).
    - Eixo X: linha de base + primeiro/último rótulo de tempo, quando houver.
    `valores` é série (ex: pico por hora). Remostra para `largura` colunas.
    """
    valores = list(valores or [])
    if not valores:
        return Panel(Text("Sem dados no período."), title=titulo, border_style="blue")
    largura = max(1, int(largura))
    altura = max(1, int(altura))
    if len(valores) > largura:
        valores = valores[-largura:]
    elif len(valores) < largura:
        valores = [0.0] * (largura - len(valores)) + valores

    def altura_coluna(v):
        try:
            pct = float(v)
        except (TypeError, ValueError):
            pct = 0.0
        pct = max(0.0, min(100.0, pct))
        return int(round(pct / 100 * altura))

    linhas = []
    for nivel in range(altura, 0, -1):
        pct_topo = nivel / altura * 100
        linha = "".join("█" if altura_coluna(v) >= nivel else " " for v in valores)
        linhas.append(f"{pct_topo:>3.0f}% │{linha.rstrip()}")
    linhas.append(f"  0% └{'─' * largura}")
    if rotulos:
        rotulos = list(rotulos)
        if len(rotulos) >= 2:
            linhas.append(f"{rotulos[0]} → {rotulos[-1]}")
        else:
            linhas.append(str(rotulos[0]))
    return Panel(Text("\n".join(linhas)), title=titulo, border_style="blue")


def render_tabela_ranking(ranking):
    """Tabela de ranking de rotinas (ordenada por duração total)."""
    tabela = Table(title="Ranking de rotinas (duração total)", show_header=True)
    tabela.add_column("Rotina")
    tabela.add_column("Exec", justify="right")
    tabela.add_column("Duração total (s)", justify="right")
    tabela.add_column("CPU total (s)", justify="right")
    tabela.add_column("RAM média (MB)", justify="right")
    for item in ranking or []:
        tabela.add_row(
            str(item.get("rotina", "")),
            str(item.get("execucoes", 0)),
            f"{float(item.get('duracao_total_s', 0.0)):.1f}",
            f"{float(item.get('cpu_total_s', 0.0)):.1f}",
            f"{float(item.get('ram_media_mb', 0.0)):.1f}",
        )
    return tabela
