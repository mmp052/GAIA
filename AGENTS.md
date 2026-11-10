# GAIA

GAIA - Gestão e Assistência com Inteligência Artificial. App desktop em Python 3.12 com PyWebview + HTML/CSS/JavaScript puro no frontend. Busca não-lidos no Gmail e resume com NLTK, com monitor de CPU/RAM em tempo real e histórico.

Visão: assistente permanente em processo único — app nativo + threads daemon (scheduler + monitor). Rotinas nunca abrem UI ou pedem input; a ponte `GaiaBridge` fornece dados estruturados para o JavaScript e as ações de execução passam por workers.

> **Este arquivo = convenções estáveis apenas.** Detalhe por módulo (valores, fluxos, thresholds, janelas) vive na docstring do módulo e em `gaia/config.py` — não duplique aqui, senão a cada feature nova ele precisa de update. Informação global fica no `~/.config/opencode/AGENTS.md`; repo-wide aqui na raiz; mais específico, junto do código (o OpenCode combina os `AGENTS.md` por proximidade).

## Comandos

```bash
.venv/bin/pip install -r requirements.txt   # deps (pywebview/Qt no Linux, nltk, google-*, psutil)
.venv/bin/python main.py                     # janela nativa PyWebview
.venv/bin/python -m pytest -q                # deve passar tudo
```

- Use sempre `.venv/bin/python`; o `python3` do sistema não tem as deps.
- Testes: `pytest.ini` (`pythonpath=.`, `testpaths=tests`). Testes de contrato da UI em `tests/test_webview.py`; demais em `tests/test_gaia.py`, `tests/test_main.py`, `tests/test_import.py`. Verificação rápida offline:
  ```bash
  .venv/bin/python -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8')) for p in pathlib.Path('gaia').rglob('*.py')]; ast.parse(open('main.py',encoding='utf-8').read()); print('syntax OK')"
  ```
- `import main` é silencioso: a janela só abre em `main()` sob `if __name__ == "__main__"`. Importar `gaia.core.*` não inicia scheduler/monitor/janela.

## Arquitetura (convenção estável)

- `main.py`: só wiring (`criar_monitor`, `criar_app_pywebview`, `executar_pywebview`, `main`, wrappers medidos). Regra de negócio mora em `gaia/`.
- `gaia/core/`: tecnologias reutilizáveis e puras/testáveis (coleta, NLP, Gmail, storage, histórico). Sem UI, sem efeitos de janela.
- `gaia/routines/`: casos de uso não-interativos que orquestram `core/`. Recebem parâmetros por código e `on_progress(msg)`; retornam dicts estruturados para o frontend.
- `gaia/ui/webview_app.py`: janela PyWebview e `GaiaBridge` — JSON simples para JS. `gaia/ui/web/`: `index.html`, `style.css`, `app.js` (HTML/CSS/JS puro, sem framework/bundler).
- `gaia/config.py`: única fonte de constantes (frases, thresholds, intervalos, janelas, nomes de arquivos). **Ler daqui; não copiar valores para cá.**
- Persistência via `gaia/core/storage.py` (JSON/JSONL). Threads daemon não bloqueiam a UI (`scheduler.py` + sampler do `Monitor`).

## Estrutura (só onde olhar)

```
main.py                         # wiring fino (entrypoint PyWebview)
gaia/
  config.py                     # constantes — ver aqui os valores atuais
  scheduler.py                  # Scheduler + deve_disparar() (6h)
  core/                         # gmail_*.py, email_extract.py, nlp.py, blacklist.py, storage.py,
                                # monitor.py (coleta CPU/RAM/GAIA), historico.py (hoje+ontem)
  routines/                     # resumidor_emails.py (não-interativo; on_progress)
  ui/                           # webview_app.py + web/ (index.html, style.css, app.js)
tests/                          # test_webview.py = contrato da janela/bridge
```

## Domínios (resumo estável; ver docstring do módulo pro detalhe)

- **Gmail OAuth:** `credentials.json` (installed) gera `token.json` na 1ª execução (`core/gmail_auth::obter_credenciais`). Escopos readonly+modify; se mudar escopo, apagar `token.json`. `AccessDeniedError` = usuário negou no Google (instruir **Permitir**; se "não verificado", `Avançado > Ir para o projeto`).
- **Resumidor** (`routines/resumidor_emails.py`, `core/gmail_client.py`, `core/nlp.py`, `core/blacklist.py`, `core/storage.py`): fluxo PyWebview busca as últimas 24h e nunca pergunta em terminal. `Ler último resumo` só lê `resumo_dia_*.json` via bridge; `Buscar novos agora` abre confirmação e executa em worker.
- **Monitor/Histórico** (`core/monitor.py`, `core/historico.py`, `ui/webview_app.py::GaiaBridge`, `ui/web/*`): coleta em background + números grandes, gráficos de linha em `<canvas>` e ranking no histórico; JS consulta a ponte periodicamente. Valores atuais (intervalos, thresholds, janela, dias) estão em `core/*` + `config.py`.
- **Arquivos pessoais:** `.gitignore` ignora `*.json` e `*.jsonl` (nunca commitar `credentials.json`, `token.json`, listas negras/permitidas, resumos, `monitor_*.jsonl`). `mensagens.json` é legado (~462MB) — não carregar em teste.

## Renderização (PyWebview + HTML/CSS/JS)

- Entrada: home estilo HUD/J.A.R.V.I.S. — holograma procedural da GAIA (esfera de energia roxa renderizada com Arcade: shader GLSL (glow do contorno e do núcleo) + teia plexus em OpenGL, 120 frames com alpha embutido em loop seamless, sempre reativa ao envelope do MP3) com o monitor à esquerda (`MONITOR`, CPU/RAM ao vivo); as rotinas orbitam a esfera como planetas — esfera glossy mini com ícone (envelope = Resumidor, gráfico = Histórico), badge com a tecla, órbita elíptica procedural distinta por rotina (PRNG com seed fixa) e clique para abrir — teclas `1`/`2` seguem válidas. O envelope (`assets/loser_envelope.js`, sem tocar áudio, gerado por `tools/gerar_envelope_gaia.py`; frames por `tools/gerar_esfera_gaia.py`) infla o núcleo e acelera a energia nos graves; a iluminação ambiente da home é derivada da esfera (gradiente radial no canvas modulado pelo envelope). Selecionar nunca executa rotina; abre a tela. `Esc` volta, `q` sai. Tema escuro único.
- Resumidor: `Ler último resumo` lê JSON salvo; `Buscar novos agora` abre modal `Sim, executar` / `Não`. Execução em thread (`GaiaBridge.iniciar_busca`) e JS faz polling com `busca_estado()`; progresso aparece na tela.
- Leitura: lista de emails do resumo, um por vez; `n`/`p` navegam; botão "Abrir no Gmail" chama a ponte e `webbrowser`. Conteúdo dinâmico entra no DOM via `textContent`, nunca `innerHTML`.
- Histórico: worker separado (`iniciar_historico`/`historico_estado`) para ler JSONL sem congelar a janela; gráficos de linha em `<canvas>` com eixos X/Y, grade pontilhada e tooltip sob hover, ranking textual, `r` recarrega.
- Linux usa Qt/PyQtWebEngine por pip (`gui="qt"` em `GaiaWebviewApp.run()`) para não exigir `gi` no venv; outras plataformas usam o backend padrão do PyWebview.
- Novas rotinas: crie em `gaia/routines/`, sem UI/input, exponha na ponte (`GaiaBridge`) + JS (`app.js`) e registre em `main::criar_app_pywebview()`; persistência via `gaia/core/storage.py`.

## Regras gerais de desenvolvimento

- Você não pode escrever nenhum código até que tenha escrito um teste de unidade que falhe.
- Você não pode escrever mais de um teste de unidade do que o necessário para falhar (e não compilar é falhar).
- Você não pode escrever mais código do que o suficiente para fazer o teste de unidade que falhou passar.
- Sempre que achar um bug faça um teste que reproduz o bug e que só passa quando o bug não acontecer.
- Novas rotinas: crie em `gaia/routines/`, reutilize `gaia/core/` (escrever 1 vez), exponha na ponte (`GaiaBridge`) + front e registre em `main::criar_app_pywebview()`. Persistência via `gaia/core/storage.py`.
- Nova funcionalidade: docstring no módulo novo + constante em `config.py` + teste em `tests/test_gaia.py`. **Só tocar neste `AGENTS.md` se a convenção estável mudar.**
