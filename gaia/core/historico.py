"""Histórico hoje+ontem — núcleo puro (filtragem, agregação, ranking).

Lê amostras de `monitor_historico.jsonl` e logs de `monitor_rotinas.jsonl`.
Tudo testável com listas em memória, sem tocar disco/rede.
"""

from datetime import datetime


def _parse_data(timestamp):
    if not timestamp:
        return None
    try:
        return datetime.fromisoformat(str(timestamp)).date()
    except (ValueError, TypeError):
        return None


def _parse_dt(timestamp):
    if not timestamp:
        return None
    try:
        return datetime.fromisoformat(str(timestamp))
    except (ValueError, TypeError):
        return None


def filtrar_hoje_ontem(amostras, hoje=None):
    """Mantém só amostras com data hoje ou ontem (por `timestamp` local)."""
    if hoje is None:
        hoje = datetime.now().date()
    alvos = {hoje, _ontem(hoje)}
    resultado = []
    for amostra in amostras or []:
        data = _parse_data(amostra.get("timestamp"))
        if data in alvos:
            resultado.append(amostra)
    return resultado


def _ontem(hoje):
    from datetime import timedelta

    return hoje - timedelta(days=1)


def resumo_historico(amostras):
    """Pico/média de CPU e RAM + total de amostras."""
    amostras = list(amostras or [])
    if not amostras:
        return {"cpu_pico": 0.0, "cpu_media": 0.0, "ram_pico": 0.0, "ram_media": 0.0, "total": 0}
    cpus = [float(a.get("cpu_percent", 0.0)) for a in amostras]
    rams = [float(a.get("ram_percent", 0.0)) for a in amostras]
    return {
        "cpu_pico": max(cpus),
        "cpu_media": sum(cpus) / len(cpus),
        "ram_pico": max(rams),
        "ram_media": sum(rams) / len(rams),
        "total": len(amostras),
    }


def agregar_por_hora(amostras):
    """Agrupa por hora cheia: hora, pico e média de CPU/RAM (ordenado)."""
    por_hora = {}
    for amostra in amostras or []:
        dt = _parse_dt(amostra.get("timestamp"))
        if dt is None:
            continue
        chave = dt.strftime("%Y-%m-%d %H:00")
        por_hora.setdefault(chave, []).append(amostra)
    buckets = []
    for hora in sorted(por_hora):
        grupo = por_hora[hora]
        cpus = [float(a.get("cpu_percent", 0.0)) for a in grupo]
        rams = [float(a.get("ram_percent", 0.0)) for a in grupo]
        buckets.append(
            {
                "hora": hora,
                "cpu_pico": max(cpus),
                "cpu_media": sum(cpus) / len(cpus),
                "ram_pico": max(rams),
                "ram_media": sum(rams) / len(rams),
                "n": len(grupo),
            }
        )
    return buckets


def ranking_rotinas(logs):
    """Soma por rotina e ordena por duração total desc (ranking de vilões)."""
    acumulado = {}
    for log in logs or []:
        nome = log.get("rotina") or "desconhecida"
        item = acumulado.setdefault(nome, {"rotina": nome, "execucoes": 0, "duracao_total_s": 0.0, "cpu_total_s": 0.0, "_ram_soma": 0.0})
        item["execucoes"] += 1
        item["duracao_total_s"] += float(log.get("duracao_s", 0.0))
        item["cpu_total_s"] += float(log.get("cpu_s", 0.0))
        item["_ram_soma"] += float(log.get("ram_mb", 0.0))
    ranking = []
    for item in acumulado.values():
        ranking.append(
            {
                "rotina": item["rotina"],
                "execucoes": item["execucoes"],
                "duracao_total_s": item["duracao_total_s"],
                "cpu_total_s": item["cpu_total_s"],
                "ram_media_mb": item["_ram_soma"] / item["execucoes"] if item["execucoes"] else 0.0,
            }
        )
    ranking.sort(key=lambda r: r["duracao_total_s"], reverse=True)
    return ranking


def obter_historico_completo(hoje=None, caminho_amostras=None, caminho_rotinas=None):
    """Lê arquivos JSONL, filtra hoje+ontem e devolve resumo/buckets/ranking."""
    from gaia.config import MONITOR_ARQUIVO_HISTORICO, MONITOR_ARQUIVO_ROTINAS
    from gaia.core.storage import carregar_amostras_monitor, carregar_logs_rotina

    if hoje is None:
        hoje = datetime.now().date()
    if caminho_amostras is None:
        caminho_amostras = MONITOR_ARQUIVO_HISTORICO
    if caminho_rotinas is None:
        caminho_rotinas = MONITOR_ARQUIVO_ROTINAS
    amostras = filtrar_hoje_ontem(carregar_amostras_monitor(limite=None, caminho=caminho_amostras), hoje=hoje)
    logs = [log for log in (carregar_logs_rotina(limite=None, caminho=caminho_rotinas) or []) if _parse_data(log.get("timestamp")) in {hoje, _ontem(hoje)}]
    return {
        "amostras": amostras,
        "logs": logs,
        "resumo": resumo_historico(amostras),
        "por_hora": agregar_por_hora(amostras),
        "ranking": ranking_rotinas(logs),
    }
