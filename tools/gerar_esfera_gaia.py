#!/usr/bin/env python3
"""Gera os frames do holograma GAIA com Arcade (OpenGL).

Renderiza um loop suave (seamless) de uma esfera de energia roxa — teia de
nós do plexus com halo, núcleo pulsante — e grava tudo em
`gaia/ui/web/assets/orb/frame_###.webp` com fundo preto puro, pensado para
ser composto no frontend com blending aditivo (`globalCompositeOperation =
"lighter"`), como os motores de partículas de jogos (estilo Arcade).

A reatividade ao envelope sonoro acontece em runtime no JavaScript — estes
frames são o "palco" animado.

Dependências (só para gerar, não em runtime):
    .venv/bin/pip install arcade pillow

Uso:
    .venv/bin/python tools/gerar_esfera_gaia.py [--frames 120] [--size 560]
"""

import argparse
import ctypes
import math
import sys
from pathlib import Path

FRAMES_PADRAO = 120
TAMANHO_PADRAO = 560
TOTAL_NOS = 118
ANGULO_DOURADO = math.pi * (3 - math.sqrt(5))
FPS = 30.0

# Matemática do holograma adaptada a roxo GAIA: anéis concêntricos de energia
# (senoides radiais), cresta de borda (edgeGlow) e núcleo quente (coreGlow),
# como no shader de referência. Constantes temporais em múltiplos de 2π/LOOP_T
# para loop seamless (LOOP_T = frames / FPS = 4.0 s).
FRAGMENT_SHADER = """
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // Normaliza para -1..1 mantendo a proporção (igual ao shader original).
    vec2 uv = (fragCoord * 2.0 - iResolution.xy) / iResolution.y;
    float d = length(uv);

    // Nada de anéis/raios emanando do centro: só o contorno da esfera e o núcleo quente.
    float disco = smoothstep(0.52, 0.34, d);
    float edgeGlow = min(0.032 / abs(d - 0.47), 2.2);   // cresta no contorno real da esfera
    float coreGlow = min(0.012 / max(d, 0.02), 2.0);    // núcleo superquente

    float finalAlpha = edgeGlow * 0.16 + coreGlow * disco;

    // Paleta GAIA: violeta profundo → lilás → quase-branco; franja azul nas sombras.
    vec3 profundo = vec3(0.30, 0.10, 0.78);
    vec3 claro = vec3(0.74, 0.60, 1.0);
    vec3 quente = vec3(0.97, 0.94, 1.0);
    vec3 hologramColor = mix(profundo, claro, clamp(coreGlow * 0.5, 0.0, 1.0));
    hologramColor += vec3(0.45, 0.30, 0.95) * edgeGlow * 0.18;                    // aro violeta
    hologramColor = mix(hologramColor, vec3(0.0, 0.55, 1.0), 0.12 * (1.0 - disco));  // franja azul JARVIS fora do disco
    hologramColor += quente * coreGlow * 0.35;

    fragColor = vec4(hologramColor * finalAlpha, clamp(finalAlpha * 0.85, 0.0, 1.0));
}
"""


def _nos_fibonacci():
    """Distribuição uniforme de nós numa esfera unitária (determinística)."""
    nos = []
    for indice in range(TOTAL_NOS):
        y = 1 - (indice / (TOTAL_NOS - 1)) * 2
        raio = math.sqrt(max(0.0, 1 - y * y))
        theta = ANGULO_DOURADO * indice
        nos.append(
            {
                "x": math.cos(theta) * raio,
                "y": y,
                "z": math.sin(theta) * raio,
                "fase": indice * 2.399,
                "deriva": 0.03 + (indice % 7) * 0.007,
            }
        )
    return nos


def _rotacionar(node, rotacao_y, inclinacao):
    cos_y, sin_y = math.cos(rotacao_y), math.sin(rotacao_y)
    x = node["x"] * cos_y - node["z"] * sin_y
    z = node["x"] * sin_y + node["z"] * cos_y
    cos_i, sin_i = math.cos(inclinacao), math.sin(inclinacao)
    y = node["y"] * cos_i - z * sin_i
    z = node["y"] * sin_i + z * cos_i
    return {"x": x, "y": y, "z": z}


def _profundidade(z):
    frente = min(1.0, max(0.0, (z + 1) / 2))
    return 0.05 + 0.95 * (frente**1.7)


def _capturar_framebuffer(largura, altura):
    """Captura o framebuffer e embute A = max(R, G, B).

    Como o palco é luz sobre preto, a luminância vira o próprio alpha:
    fundo preto fica transparente e o glow compõe limpo com source-over,
    sem truques de blend no navegador.
    """
    import numpy as np
    import pyglet.gl as GL

    buf = ctypes.create_string_buffer(largura * altura * 3)
    GL.glReadPixels(0, 0, largura, altura, GL.GL_RGB, GL.GL_UNSIGNED_BYTE, buf)
    dados = np.frombuffer(buf.raw, dtype=np.uint8).reshape(altura, largura, 3)
    alfa = dados.max(axis=2, keepdims=True)
    rgba = np.concatenate([dados, alfa], axis=2)
    from PIL import Image

    imagem = Image.fromarray(rgba, "RGBA")
    return imagem.transpose(Image.FLIP_TOP_BOTTOM)


def renderizar(destino: Path, frames: int, tamanho: int) -> None:
    import arcade

    nos = _nos_fibonacci()
    destino.mkdir(parents=True, exist_ok=True)

    raio_esfera = tamanho * 0.235
    centro = tamanho / 2
    progresso_holder = {"indice": 0}

    def projetar(p):
        perspectiva = 6.0 / (6.0 - p["z"])
        return (centro + p["x"] * raio_esfera * perspectiva, centro + p["y"] * raio_esfera * perspectiva)

    # Texturas de gradiente radial (geradas uma vez, reusadas em todos os frames).
    tex_halo = arcade.make_soft_circle_texture(256, (124, 58, 237), 150, 0)
    tex_halo_claro = arcade.make_soft_circle_texture(256, (167, 139, 250), 95, 0)
    tex_nucleo = arcade.make_soft_circle_texture(128, (196, 160, 255), 255, 0)
    tex_nucleo_quente = arcade.make_soft_circle_texture(64, (240, 235, 255), 255, 70)
    tex_brasa = arcade.make_soft_circle_texture(64, (255, 255, 255), 255, 0)
    tex_no = arcade.make_soft_circle_texture(32, (216, 205, 254), 255, 0)

    def desenhar_textura(tex, x, y, largura, altura, alfa=255):
        arcade.draw_texture_rect(tex, arcade.LBWH(x - largura / 2, y - altura / 2, largura, altura), alpha=alfa)

    def desenhar_frame(indice_frame: int) -> None:
        progresso = indice_frame / frames
        rotacao = 2 * math.pi * progresso  # uma volta completa por loop → seamless
        inclinacao = 0.38 + 0.05 * math.sin(2 * math.pi * 2 * progresso)
        pulso = 1 + 0.1 * math.sin(2 * math.pi * 2 * progresso)

        # Halo externo e interno (respiração lenta e simétrica, harmônicos inteiros).
        desenhar_textura(tex_halo, centro, centro, raio_esfera * 3.3 * pulso, raio_esfera * 3.3 * pulso, 150)
        desenhar_textura(tex_halo_claro, centro, centro, raio_esfera * 2.1 * pulso, raio_esfera * 2.1 * pulso, 120)

        # Núcleo quente: branco no meio, violeta ao redor.
        desenhar_textura(tex_nucleo, centro, centro, raio_esfera * 0.95 * pulso, raio_esfera * 0.95 * pulso, 235)
        desenhar_textura(tex_nucleo_quente, centro, centro, raio_esfera * 0.5 * pulso, raio_esfera * 0.5 * pulso, 255)
        desenhar_textura(tex_brasa, centro, centro, raio_esfera * 0.17 * pulso, raio_esfera * 0.17 * pulso, 255)


        # Nós em deriva suave (harmônicos inteiros → loop perfeito).
        rotacionados = []
        for no in nos:
            deriva = 1 + no["deriva"] * math.sin(2 * math.pi * progresso * 2 + no["fase"])
            rotacionados.append(_rotacionar({"x": no["x"] * deriva, "y": no["y"] * deriva, "z": no["z"] * deriva}, rotacao, inclinacao))

        projetados = [projetar(p) for p in rotacionados]

        # Teia: arestas entre vizinhos (dist < 0.56 na esfera unitária).
        limite = 0.56
        for i in range(TOTAL_NOS):
            a = rotacionados[i]
            for j in range(i + 1, TOTAL_NOS):
                b = rotacionados[j]
                dist = math.dist((a["x"], a["y"], a["z"]), (b["x"], b["y"], b["z"]))
                if dist >= limite:
                    continue
                proximidade = 1 - dist / limite
                profundidade = _profundidade((a["z"] + b["z"]) / 2)
                alfa = min(215, int(255 * proximidade * proximidade * profundidade * 0.85))
                if alfa < 12:
                    continue
                x1, y1 = projetados[i]
                x2, y2 = projetados[j]
                arcade.draw_line(x1, y1, x2, y2, (140, 109, 235, alfa // 3), max(2, int(2 + proximidade * 3)))
                arcade.draw_line(x1, y1, x2, y2, (212, 200, 254, alfa), max(1, int(1 + proximidade * 1.4)))

        # Nós luminosos com twinkle em harmônico inteiro.
        for indice, (no, p) in enumerate(zip(rotacionados, projetados)):
            profundidade = _profundidade(no["z"])
            cintilar = 0.7 + 0.3 * math.sin(2 * math.pi * progresso * 3 + indice * 1.93)
            alfa = min(255, int(225 * profundidade * cintilar))
            raio = (1.5 + 3.4 * ((no["z"] + 1) / 2)) * (1 + 0.25 * math.sin(2 * math.pi * progresso * 3 + indice))
            if alfa < 16:
                continue
            desenhar_textura(tex_no, p[0], p[1], raio * 6, raio * 6, max(20, alfa // 2))
            desenhar_textura(tex_brasa, p[0], p[1], raio * 1.7, raio * 1.7, alfa)

    class Gerador(arcade.View):
        def __init__(self):
            super().__init__()
            self.shader = None

        def on_draw(self):
            self.clear()
            indice = progresso_holder["indice"]
            if self.shader is None:
                from arcade.experimental import Shadertoy

                self.shader = Shadertoy((tamanho, tamanho), FRAGMENT_SHADER)
            self.shader.render(time=indice / frames * (frames / FPS))
            desenhar_frame(indice)
            imagem = _capturar_framebuffer(tamanho, tamanho)
            imagem.save(destino / f"frame_{indice:03d}.webp", "WEBP", quality=80, method=4)
            progresso_holder["indice"] = indice + 1
            if (indice + 1) % 20 == 0:
                print(f"frames {indice + 1}/{frames}", flush=True)
            if indice + 1 >= frames:
                arcade.exit()

    win = arcade.Window(tamanho, tamanho, "gaia-orb-gen", visible=False, vsync=False, antialiasing=False, samples=0)
    arcade.set_background_color((0, 0, 0))
    win.show_view(Gerador())
    arcade.run()


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera o loop do holograma GAIA com Arcade (OpenGL).")
    parser.add_argument("--frames", type=int, default=FRAMES_PADRAO)
    parser.add_argument("--size", type=int, default=TAMANHO_PADRAO)
    parser.add_argument("--saida", type=Path, default=Path(__file__).resolve().parents[1] / "gaia" / "ui" / "web" / "assets" / "orb")
    args = parser.parse_args()

    if args.frames < 24 or args.size < 160:
        parser.error("use ao menos 24 frames e tamanho 160")

    renderizar(args.saida, args.frames, args.size)
    print(f"{args.frames} frames em {args.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
