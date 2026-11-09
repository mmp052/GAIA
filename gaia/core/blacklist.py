import json
import re
from pathlib import Path


def extrair_email(remetente):
    m = re.search(r"<([^>]+)>", remetente)
    return (m.group(1) if m else remetente).strip().lower()


def carregar_lista_negra(caminho="lista_negra.json"):
    if not Path(caminho).is_file():
        return []
    try:
        return json.load(open(caminho, encoding="utf-8"))
    except Exception:
        return []


def salvar_lista_negra(lista, caminho="lista_negra.json"):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)


def carregar_lista_permitida(caminho="lista_permitida.json"):
    if not Path(caminho).is_file():
        return []
    try:
        return json.load(open(caminho, encoding="utf-8"))
    except Exception:
        return []


def salvar_lista_permitida(lista, caminho="lista_permitida.json"):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)


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


def esta_permitido(remetente, lista_permitida):
    if not lista_permitida:
        return False
    email = extrair_email(remetente)
    for item in lista_permitida:
        item = item.strip().lower()
        if not item:
            continue
        if item.startswith("@"):
            if email.endswith(item):
                return True
        elif email == item:
            return True
    return False
