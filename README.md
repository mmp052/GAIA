# GAIA
GAIA - Gestão e Assistência com Inteligência Artificial

# Descrição
A ideia desse projeto é fazer como o nome diz um assistente de inteligencia artificial. primeiro vou fazer scripts puros pra automatizar processos do dia a dia que eu achar util e depois vou incrementando. de começo penso em fazer uma cli pra interagir com os scripts.

# modulo 1
Um resumidor de emails. todo dia vai entrar no meu email pegar os novos emails, usar nlp pra classificar eles e fazer um resumo no final. ai tambem integrar com agenda ou coisa do tipo. A gaia vai rodar sempre, ai eu posso manualmente pedir pra usar a função de rodar email mas ele vai fazer isso automatico todo dia as 6 da manha.

TO-DO :
fazer a pipeline pra pegar as mensagens não lidas e processar elas pra ficarem prontas pro nlp analizar.

# UI
`.venv/bin/python main.py` abre o GAIA em uma janela PyWebview com HTML/CSS/JavaScript puro: home estilo HUD com um holograma procedural da GAIA (canvas 3D — esfera de energia roxa, na linha do J.A.R.V.I.S. do MCU) com o monitor CPU/RAM/GAIA ao vivo à esquerda e as rotinas orbitando a esfera como planetas (Resumidor de Emails e Histórico, com ícone próprio, tecla indicada e clique para abrir). Os frames 3D da esfera são renderizados com a biblioteca **Arcade** (`tools/gerar_esfera_gaia.py`, loop seamless de 120 frames, alpha embutido; o campo de energia é um shader GLSL — glow no contorno e no núcleo — combinado a uma teia plexus desenhada em OpenGL) e o holograma pulsa o tempo todo no envelope de `Tame Impala – Loser (Theatre Version)` — sempre ligado, em loop, sem botão de play; o envelope (`gaia/ui/web/assets/loser_envelope.js`) é gerado offline do MP3 por `tools/gerar_envelope_gaia.py` e o app não decodifica nem toca áudio. Selecionar um planeta (ou as teclas `1`/`2`) abre a tela da rotina — nada executa sem você confirmar; leitura de emails é um por vez, com `n`/`p` para navegar e botão "Abrir no Gmail". O histórico também tem eixos X/Y, grade pontilhada e tooltip sob hover. Tema escuro único, `q` sai, `Esc` volta para a tela anterior.