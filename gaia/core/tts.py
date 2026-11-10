"""Síntese de fala (text-to-speech) local e offline via Kokoro (ONNX).

Expõe ``montar_texto`` para compor o texto lido a partir de um email do
resumo e ``falar``/``parar`` para controlar a leitura. Nada sai da máquina:
modelo e vozes ficam em ``models/``. ``falar`` sintetiza em background e a
reprodução usa um processo externo (``pw-play``/``aplay``), então ``parar``
interrompe a fala imediatamente — inclusive no fechamento do app.
"""

import re
import subprocess
import tempfile
import threading
from pathlib import Path

import soundfile

from gaia.config import TTS_LANG, TTS_MODEL, TTS_SPEED, TTS_VOICE, TTS_VOICES

_lock = threading.Lock()
_kokoro = None
_play_proc = None


def montar_texto(email):
    """Compõe o texto falado a partir de um email do resumo."""
    de = str(email.get("de") or "").split("<")[0].strip() or "remetente desconhecido"
    assunto = str(email.get("assunto") or "sem assunto").strip()
    resumo = str(email.get("resumo") or "").strip()
    partes = [f"Email de {de}.", f"Assunto: {assunto}."]
    if resumo:
        partes.append(resumo)
    return " ".join(partes)


def _carregar_kokoro():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro

        base = Path(__file__).resolve().parents[2]
        modelo = TTS_MODEL if Path(TTS_MODEL).is_absolute() else str(base / TTS_MODEL)
        vozes = TTS_VOICES if Path(TTS_VOICES).is_absolute() else str(base / TTS_VOICES)
        _kokoro = Kokoro(modelo, vozes)
    return _kokoro


def _tocador_cmd():
    import shutil

    for cmd in ("pw-play", "aplay"):
        if shutil.which(cmd):
            return cmd
    return None


def falar(texto):
    """Sintetiza e reproduz ``texto`` em background; retorna imediatamente."""
    texto = re.sub(r"\s+", " ", str(texto or "")).strip()
    if not texto:
        return {"falando": False}
    parar()

    def trabalho():
        global _play_proc
        try:
            print("[tts] carregando modelo…", flush=True)
            kokoro = _carregar_kokoro()
            print("[tts] sintetizando…", flush=True)
            amostras, taxa = kokoro.create(texto, voice=TTS_VOICE, lang=TTS_LANG, speed=TTS_SPEED)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                caminho = tmp.name
            soundfile.write(caminho, amostras, taxa)
            tocador = _tocador_cmd()
            print(f"[tts] wav={caminho} tocador={tocador}", flush=True)
            if tocador is None:
                print("[tts] nenhum tocador disponível (pw-play/aplay)", flush=True)
                return
            with _lock:
                _play_proc = subprocess.Popen([tocador, caminho], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("[tts] reproduzindo…", flush=True)
            _play_proc.wait()
            print("[tts] fim da reprodução", flush=True)
        except Exception:
            import traceback

            traceback.print_exc()

    threading.Thread(target=trabalho, name="gaia-tts", daemon=True).start()
    return {"falando": True}


def parar():
    """Interrompe a reprodução em andamento, se houver."""
    global _play_proc
    with _lock:
        proc = _play_proc
        _play_proc = None
    if proc is not None:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    return {"falando": False}
