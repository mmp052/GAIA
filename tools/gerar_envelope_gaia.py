#!/usr/bin/env python3
"""Gera o envelope sonoro que anima o holograma da GAIA (análise offline).

Lê um MP3/WAV e emite um asset JS (`window.GAIA_ENVELOPE = {...}`) com a
energia por janela de 100 ms em quatro bandas (rms, graves, médios, agudos),
normalizadas no percentil 98. O frontend consome esse "score" para pulsar o
holograma — nenhum áudio é reproduzido pela aplicação.

Dependências (só para gerar, não em runtime):
    .venv/bin/pip install numpy soundfile

Uso:
    .venv/bin/python tools/gerar_envelope_gaia.py \
        "Tame Impala - Loser (Theatre Version) 🎧Use Headphones🎧.mp3" \
        gaia/ui/web/assets/loser_envelope.js
"""

import argparse
import json
import sys
from pathlib import Path


def analisar(caminho: Path, janela_ms: int = 100) -> dict:
    import numpy as np
    import soundfile as sf

    audio, taxa = sf.read(str(caminho), always_2d=True)
    mono = audio.mean(axis=1)
    duracao_s = len(mono) / taxa

    amostras_janela = int(taxa * janela_ms / 1000)
    n_janelas = len(mono) // amostras_janela
    if n_janelas == 0:
        raise ValueError("Áudio curto demais para a janela escolhida.")

    janela = np.hanning(amostras_janela).astype(np.float64)
    espectro = np.abs(np.fft.rfft(mono[: n_janelas * amostras_janela].reshape(n_janelas, amostras_janela) * janela, axis=1))
    frequencias = np.fft.rfftfreq(amostras_janela, d=1.0 / taxa)

    def banda(faixa):
        mascara = (frequencias >= faixa[0]) & (frequencias < faixa[1])
        return espectro[:, mascara].mean(axis=1) if mascara.any() else np.zeros(n_janelas)

    graves = banda((40, 250))
    medios = banda((250, 2000))
    agudos = banda((2000, 10000))
    rms = np.sqrt((mono[: n_janelas * amostras_janela].reshape(n_janelas, amostras_janela) ** 2).mean(axis=1))

    def normalizar(coluna):
        pivo = np.percentile(coluna, 98)
        if pivo <= 1e-9:
            return np.zeros_like(coluna)
        return np.clip(coluna / pivo, 0.0, 1.0)

    frames = np.column_stack([normalizar(coluna) for coluna in (rms, graves, medios, agudos)])
    frames = np.round(frames, 3)

    return {
        "fonte": caminho.name,
        "duracao_s": round(duracao_s, 2),
        "janela_ms": janela_ms,
        "fps": round(1000 / janela_ms, 2),
        "bandas": ["rms", "graves", "medios", "agudos"],
        "frames": frames.tolist(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera o envelope JSON/JS do holograma GAIA a partir de um MP3/WAV.")
    parser.add_argument("entrada", type=Path)
    parser.add_argument("saida", type=Path)
    parser.add_argument("--janela-ms", type=int, default=100)
    args = parser.parse_args()

    if not args.entrada.is_file():
        parser.error(f"arquivo não encontrado: {args.entrada}")

    envelope = analisar(args.entrada, janela_ms=args.janela_ms)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    args.saida.write_text(f"window.GAIA_ENVELOPE = {payload};\n", encoding="utf-8")
    print(f"{envelope['frames'].__len__()} janelas · {envelope['duracao_s']}s → {args.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
