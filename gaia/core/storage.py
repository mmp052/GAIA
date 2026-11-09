import json
from datetime import datetime
from pathlib import Path


def salvar_lista_emails(lista, caminho="lista_emails.json"):
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(lista, arquivo)


def salvar_resumo_dia(dia, resumidos, ignorados, agora=None):
    if agora is None:
        agora = datetime.now()
    nome = f"resumo_dia_{agora.strftime('%Y-%m-%d')}.json"
    base_resumidos, base_ignorados = [], []
    try:
        with open(nome, encoding="utf-8") as f:
            anterior = json.load(f)
        if isinstance(anterior, dict):
            base_resumidos = anterior.get("resumidos") or []
            base_ignorados = anterior.get("ignorados") or []
    except (OSError, ValueError):
        base_resumidos, base_ignorados = [], []

    def mesclar(base, novos):
        vistos = {str(item.get("id")) for item in base if isinstance(item, dict) and item.get("id") is not None}
        resultado = list(base)
        for item in novos:
            chave = str(item.get("id")) if isinstance(item, dict) and item.get("id") is not None else None
            if chave is not None:
                if chave in vistos:
                    continue
                vistos.add(chave)
            resultado.append(item)
        return resultado

    payload = {"dia": dia, "resumidos": mesclar(base_resumidos, resumidos), "ignorados": mesclar(base_ignorados, ignorados)}
    with open(nome, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return nome


def _anexar_jsonl(registro, caminho):
    with open(caminho, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def _carregar_jsonl(limite, caminho):
    try:
        with open(caminho, encoding="utf-8") as f:
            linhas = f.readlines()
    except OSError:
        return []
    registros = []
    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue
        try:
            registros.append(json.loads(linha))
        except ValueError:
            continue
    if limite:
        return registros[-limite:]
    return registros


def anexar_monitor_amostra(amostra, caminho="monitor_historico.jsonl"):
    _anexar_jsonl(amostra, caminho)


def carregar_amostras_monitor(limite=30, caminho="monitor_historico.jsonl"):
    return _carregar_jsonl(limite, caminho)


def anexar_log_rotina(registro, caminho="monitor_rotinas.jsonl"):
    _anexar_jsonl(registro, caminho)


def carregar_logs_rotina(limite=20, caminho="monitor_rotinas.jsonl"):
    return _carregar_jsonl(limite, caminho)


def carregar_ultimo_resumo(diretorio="."):
    arquivos = sorted(Path(diretorio).glob("resumo_dia_*.json"), reverse=True)
    for arquivo in arquivos:
        if not arquivo.is_file():
            continue
        try:
            dados = json.load(open(arquivo, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(dados, dict):
            return {"dia": dados.get("dia"), "resumidos": dados.get("resumidos") or [], "ignorados": dados.get("ignorados") or [], "arquivo": arquivo.name}
    return None
