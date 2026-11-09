import base64
import html
import re


def obter_header(payload, nome):
    for h in payload.get("headers", []):
        if h.get("name", "").lower() == nome.lower():
            return h.get("value", "")
    return ""


def decodificar_base64url(dados):
    if not dados:
        return ""
    try:
        return base64.urlsafe_b64decode(dados + "=" * (-len(dados) % 4)).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _coletar_textos(payload, lista_plain, lista_html):
    mime = payload.get("mimeType", "text/plain")
    body_data = payload.get("body", {}).get("data")
    if mime == "text/plain" and body_data:
        lista_plain.append(decodificar_base64url(body_data))
    elif mime == "text/html" and body_data:
        lista_html.append(decodificar_base64url(body_data))
    for parte in payload.get("parts", []):
        _coletar_textos(parte, lista_plain, lista_html)


def limpar_html(texto_html):
    texto = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", texto_html)
    texto = re.sub(r"(?s)<[^>]+>", " ", texto)
    texto = html.unescape(texto)
    return texto


def extrair_texto_email(msg):
    lista_plain, lista_html = [], []
    _coletar_textos(msg.get("payload", {}), lista_plain, lista_html)
    texto = "\n".join(lista_plain).strip()
    if len(texto) < 50 and lista_html:
        texto = limpar_html("\n".join(lista_html))
    return texto


def limpar_texto(texto):
    texto = re.split(r"(?im)\n\s*(em 20\d\d.*escreveu:|on .*wrote:|--?\s*$|para sua segurança.*cancele|enviado do meu iphone)", texto)[0]
    texto = re.sub(r"https?://\S+", " ", texto)
    linhas = [l.strip() for l in texto.splitlines() if any(c.isalpha() for c in l)]
    texto = " ".join(linhas)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def link_email(msg_id, thread_id=None):
    ref = thread_id or msg_id
    return f"https://mail.google.com/mail/u/0/#inbox/{ref}"
