# GAIA

GAIA - Gestão e Assistência com Inteligência Artificial. CLI em Python 3.12 (`main.py` como entrypoint fino + pacote `gaia/`) com Rich no terminal. Busca não-lidos no Gmail e resume com NLTK, com monitor de CPU/RAM em tempo real e histórico.

Visão: assistente permanente em processo único — loop interativo principal + threads daemon (scheduler + monitor). Rotinas nunca chamam `input()`/`console.print()` direto: a UI injeta `prompter`/`console` (futura troca por voz + testes com fakes).

> **Este arquivo = convenções estáveis apenas.** Detalhe por módulo (valores, fluxos, thresholds, janelas) vive na docstring do módulo e em `gaia/config.py` — não duplique aqui, senão a cada feature nova ele precisa de update. Informação global fica no `~/.config/opencode/AGENTS.md`; repo-wide aqui na raiz; mais específico, junto do código (o OpenCode combina os `AGENTS.md` por proximidade).

## Comandos

```bash
.venv/bin/pip install -r requirements.txt   # deps (nltk, rich, pyfiglet, google-*, psutil)
.venv/bin/python main.py                     # menu interativo (tecla única, sem Enter)
.venv/bin/python -m pytest -q                # deve passar tudo (legados + gaia)
```

- Use sempre `.venv/bin/python`; o `python3` do sistema não tem as deps.
- Testes: `pytest.ini` (`pythonpath=.`, `testpaths=tests`). Legados em `tests/test_main.py` + `tests/test_import.py`; novos em `tests/test_gaia.py`. Verificação rápida offline:
  ```bash
  .venv/bin/python -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8')) for p in pathlib.Path('gaia').rglob('*.py')]; ast.parse(open('main.py',encoding='utf-8').read()); print('syntax OK')"
  ```
- `import main` é silencioso: banner/menu só rodam em `main()` sob `if __name__ == "__main__"`. Importar `gaia.core.*` não dispara menu/banner. `main.py` re-exporta símbolos históricos para os testes antigos continuarem verdes.

## Arquitetura (convenção estável)

- `main.py`: só wiring (`mostrar_banner`, `construir_menu`, `main`, wrappers medidos). Regra de negócio mora em `gaia/`.
- `gaia/core/`: tecnologias reutilizáveis e puras/testáveis (coleta, NLP, Gmail, storage, histórico). Sem UI, sem `input()`.
- `gaia/routines/`: casos de uso que orquestram `core/` + `ui/`. Recebem `console`/`prompter`/`pager_input` injetáveis; `processar_mensagem()`-style puros são testáveis sem rede.
- `gaia/ui/`: só renderização Rich (`get_console()` singleton, `menu.py`, `render.py`, `monitor_render.py`, `historico_render.py`, `screens.py`).
- `gaia/config.py`: única fonte de constantes (frases, thresholds, intervalos, janelas, nomes de arquivos). **Ler daqui; não copiar valores para cá.**
- Persistência via `gaia/core/storage.py` (JSON/JSONL). Threads daemon não bloqueiam o menu (`scheduler.py` + sampler do `Monitor`).

## Estrutura (só onde olhar)

```
main.py                         # wiring fino (banner, menu, Live + tecla única)
gaia/
  config.py                     # constantes — ver aqui os valores atuais
  scheduler.py                  # Scheduler + deve_disparar() (6h)
  core/                         # gmail_*.py, email_extract.py, nlp.py, blacklist.py, storage.py,
                                # monitor.py (coleta CPU/RAM/GAIA), historico.py (hoje+ontem)
  routines/                     # resumidor_emails.py, historico.py — ver docstring de cada uma
  ui/                           # console.py, menu.py, render.py, monitor_render.py,
                                # historico_render.py, screens.py, progress.py, erros.py
tests/
```

## Domínios (resumo estável; ver docstring do módulo pro detalhe)

- **Gmail OAuth:** `credentials.json` (installed) gera `token.json` na 1ª execução (`core/gmail_auth::obter_credenciais`). Escopos readonly+modify; se mudar escopo, apagar `token.json`. `AccessDeniedError` = usuário negou no Google (instruir **Permitir**; se "não verificado", `Avançado > Ir para o projeto`).
- **Resumidor** (`routines/resumidor_emails.py`, `core/gmail_client.py`, `core/nlp.py`, `core/blacklist.py`, `core/storage.py`): ver docstring da rotina. Ponto essencial: manual vs scheduler diferem só no modo de busca/interação (nunca hardcodar fluxo aqui — ler o módulo).
- **Monitor/Histórico** (`core/monitor.py`, `core/historico.py`, `ui/monitor_render.py`, `ui/historico_render.py`, `main::loop_menu_com_monitor`): coleta em background + painel Live; histórico lê os JSONL e filtra/agrega. Valores atuais (intervalos, thresholds, janela, dias) estão em `core/*` + `config.py`.
- **Arquivos pessoais:** `.gitignore` ignora `*.json` e `*.jsonl` (nunca commitar `credentials.json`, `token.json`, listas negras/permitidas, resumos, `monitor_*.jsonl`). `mensagens.json` é legado (~462MB) — não carregar em teste.

## Renderização (Rich)

- Link clicável: `Text("...", style=f"link {url}")` (OSC 8). **Não** usar `[link url]...[/link]` (quebra no Rich 15). Para cor inline, usar `Text.from_markup()` — `Text()` puro mostra o markup cru.
- Escapar dinâmicas com `rich.markup.escape` antes de meter em markup (exceto blocos `█▁▂` da sparkline).
- Menu principal é `Live` contínuo com **tecla única** (`main::ler_tecla` + `tecla_para_acao`, sem Enter): nunca ler `input()` de linha em thread enquanto o Live redesenha — apaga a digitação. Live só para antes de rotinas e volta ao sair.

## Regras gerais de desenvolvimento

- Você não pode escrever nenhum código até que tenha escrito um teste de unidade que falhe.
- Você não pode escrever mais de um teste de unidade do que o necessário para falhar (e não compilar é falhar).
- Você não pode escrever mais código do que o suficiente para fazer o teste de unidade que falhou passar.
- Sempre que achar um bug faça um teste que reproduz o bug e que só passa quando o bug não acontecer.
- Novas rotinas: crie em `gaia/routines/`, reutilize `gaia/core/` (escrever 1 vez), apresente via `gaia/ui/`, registre em `main::construir_menu()` (e `tecla_para_acao` se for tecla única). Persistência via `gaia/core/storage.py`.
- Nova funcionalidade: docstring no módulo novo + constante em `config.py` + teste em `tests/test_gaia.py`. **Só tocar neste `AGENTS.md` se a convenção estável mudar.**
