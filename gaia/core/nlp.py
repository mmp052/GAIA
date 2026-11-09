import math

import nltk
from nltk.corpus import stopwords
from nltk.probability import FreqDist
from nltk.tokenize import sent_tokenize

from gaia.config import N_FRASES_RESUMO
from gaia.core.email_extract import limpar_texto


def _garantir_recursos_nltk():
    for recurso in ("punkt_tab", "punkt", "stopwords"):
        try:
            nltk.data.find(f"tokenizers/{recurso}")
        except LookupError:
            nltk.download(recurso, quiet=True)


_garantir_recursos_nltk()


def detectar_idioma(texto):
    texto_lower = " " + texto.lower() + " "
    palavras_pt = [" de ", " que ", " para ", " com ", " você ", " obrigado", " não ", " este ", " esta "]
    palavras_en = [" the ", " and ", " for ", " with ", " you ", " thank", " this ", " that ", " are "]
    score_pt = sum(texto_lower.count(p) for p in palavras_pt)
    score_en = sum(texto_lower.count(p) for p in palavras_en)
    return "english" if score_en > score_pt else "portuguese"


def gerar_resumo_extrativo(texto, n_frases=N_FRASES_RESUMO):
    texto_limpo = limpar_texto(texto)
    if not texto_limpo or len(texto_limpo) < 30:
        return texto_limpo[:500], detectar_idioma(texto_limpo)

    idioma = detectar_idioma(texto_limpo)
    try:
        frases = sent_tokenize(texto_limpo, language=idioma)
    except Exception:
        frases = sent_tokenize(texto_limpo)

    frases_validas = [f.strip() for f in frases if 30 <= len(f.strip()) <= 1500]
    if not frases_validas:
        return texto_limpo[:500], idioma
    if len(frases_validas) <= n_frases:
        return " ".join(frases_validas), idioma

    stop = set(stopwords.words(idioma))
    palavras = [w.lower() for w in nltk.word_tokenize(texto_limpo) if w.isalpha() and w.lower() not in stop]
    freq = FreqDist(palavras)

    pontuadas = []
    for idx, frase in enumerate(frases_validas):
        toks = [w.lower() for w in nltk.word_tokenize(frase) if w.isalpha() and w.lower() not in stop]
        if not toks:
            continue
        score = sum(freq[t] for t in toks) / math.sqrt(len(toks))
        if idx < 3:
            score *= 1.1
        pontuadas.append((idx, score))

    if not pontuadas:
        return " ".join(frases_validas[:n_frases]), idioma

    pontuadas.sort(key=lambda x: x[1], reverse=True)
    escolhidas = sorted(idx for idx, _ in pontuadas[:n_frases])
    resumo = " ".join(frases_validas[i] for i in escolhidas)
    return resumo, idioma
