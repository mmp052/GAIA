"""Renderização do monitor em tempo real (dashboard Essencial)."""

from rich.panel import Panel
from rich.text import Text

from gaia.config import MONITOR_JANELA_SPARKLINE, MONITOR_THRESHOLD_AVISO, MONITOR_THRESHOLD_CRITICO

_BLOCOS = "▁▂▃▄▅▆▇█"


def gerar_sparkline(valores, largura=None):
    """Transforma lista de percentuais 0-100 em sparkline de blocos.

    Com `largura`, retorna exatamente `largura` caracteres (últimos valores,
    à esquerda completado com blocos baixos) para o painel não crescer.
    Sem `largura`, mantém compat: lista vazia → "".
    """
    if not valores:
        if largura is None:
            return ""
        return _BLOCOS[0] * largura
    if largura is not None:
        valores = list(valores)[-largura:] if len(valores) > largura else [0.0] * (largura - len(valores)) + list(valores)
    chars = []
    for v in valores:
        try:
            pct = float(v)
        except (TypeError, ValueError):
            pct = 0.0
        pct = max(0.0, min(100.0, pct))
        idx = int(pct / 100 * (len(_BLOCOS) - 1))
        chars.append(_BLOCOS[idx])
    return "".join(chars)


def cor_por_threshold(valor, aviso=MONITOR_THRESHOLD_AVISO, critico=MONITOR_THRESHOLD_CRITICO):
    """Só visual: <aviso normal, aviso-critico amarelo, >=critico vermelho."""
    valor = float(valor)
    if valor >= critico:
        return "red"
    if valor >= aviso:
        return "yellow"
    return "green"


def formatar_mb(total_bytes):
    return f"{total_bytes / 1024 / 1024:.0f}MB"


def render_monitor(amostra, historico_cpu=None, historico_ram=None, aviso=MONITOR_THRESHOLD_AVISO, critico=MONITOR_THRESHOLD_CRITICO, janela=MONITOR_JANELA_SPARKLINE):
    """Painel Rich do monitor. Aceita amostra None (sem dados ainda)."""
    historico_cpu = historico_cpu or []
    historico_ram = historico_ram or []
    spark_cpu = gerar_sparkline(historico_cpu, largura=janela)
    spark_ram = gerar_sparkline(historico_ram, largura=janela)

    if amostra is None:
        return Panel(Text("Monitor: aguardando primeira amostra..."), title="Monitor", border_style="blue")

    cpu = float(amostra.get("cpu_percent", 0.0))
    ram = float(amostra.get("ram_percent", 0.0))
    cor_cpu = cor_por_threshold(cpu, aviso, critico)
    cor_ram = cor_por_threshold(ram, aviso, critico)
    gaia_cpu = float(amostra.get("gaia_cpu_percent", 0.0))
    gaia_ram = float(amostra.get("gaia_ram_mb", 0.0))
    usada_mb = formatar_mb(amostra.get("ram_usada_bytes", 0))
    total_mb = formatar_mb(amostra.get("ram_total_bytes", 0))

    linhas = [
        f"CPU [bold {cor_cpu}]{cpu:.1f}%[/]  {spark_cpu}",
        f"RAM [bold {cor_ram}]{ram:.1f}%[/]  {spark_ram}  ({usada_mb}/{total_mb})",
        f"GAIA: CPU {gaia_cpu:.1f}% | RAM {gaia_ram:.0f}MB",
    ]
    return Panel(Text.from_markup("\n".join(linhas)), title="Monitor", border_style="blue")
