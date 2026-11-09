# GAIA

GAIA - Gestão e Assistência com Inteligência Artificial. CLI em Python com `main.py` como entrypoint fino (banner + scheduler + menu) e pacote `gaia/` modular: `core/` (tecnologias reutilizáveis), `routines/` (casos de uso que orquestram `core/`), `ui/` (renderização terminal), `scheduler.py` (tarefas em background) e `config.py` (constantes). Busca emails não lidos no Gmail, gera resumo extrativo com NLTK e renderiza no terminal com Rich.

Visão: assistente permanente em processo único (loop interativo + scheduler em thread daemon). Rotinas nunca chamam `input()`/`console.print()` direto — a UI injeta `prompter`/`console` — para permitir futura troca por voz e facilitar testes com fakes.

## Comandos

```bash
.venv/bin/pip install -r requirements.txt   # deps (nltk, rich, pyfiglet, google-*)
.venv/bin/python main.py                     # menu: 1 = Resumidor de Emails, 0 = sair
.venv/bin/python -m pytest -q                # 62 testes (47 legados + 15 gaia)
```

- Use sempre `.venv/bin/python` (Python 3.12); o `python3` do sistema não tem `nltk`.
- Testes: `pytest.ini` (`pythonpath=.`, `testpaths=tests`). Legados em `tests/test_main.py` + `tests/test_import.py`; novos em `tests/test_gaia.py`. Verificação rápida offline:
  ```bash
  .venv/bin/python -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8')) for p in pathlib.Path('gaia').rglob('*.py')]; ast.parse(open('main.py',encoding='utf-8').read()); print('syntax OK')"
  ```
- `import main` é silencioso e não bloqueia: banner/menu só rodam em `main()` sob `if __name__ == "__main__":`. Importar `gaia.core.*` não dispara menu nem banner. `main.py` re-exporta símbolos históricos (`carregar_lista_negra`, `extrair_email`, `gerar_resumo_extrativo`, `resumir_emails`, etc.) para os testes antigos continuarem verdes.

## Estrutura

```
main.py                         # wiring fino: mostrar_banner(), construir_menu(), main(), resumir_emails() wrapper
gaia/
  config.py                     # N_FRASES_RESUMO = 3
  scheduler.py                  # Scheduler(tarefa, hora=6, minuto=0) + deve_disparar()
  core/
    gmail_auth.py               # SCOPES, obter_credenciais(console) — OAuth/refresh/token
    gmail_client.py             # listar_nao_lidos(service, q), buscar_dia_mais_recente, obter/marcar
    email_extract.py            # obter_header, decodificar_base64url, _coletar_textos, limpar_html, extrair_texto_email, limpar_texto, link_email
    nlp.py                      # _garantir_recursos_nltk, detectar_idioma, gerar_resumo_extrativo
    blacklist.py                # carregar/salvar_lista_negra, extrair_email, esta_bloqueado
    storage.py                  # salvar_lista_emails, salvar_resumo_dia
  routines/
    resumidor_emails.py         # processar_mensagem() pura + resumir_emails(service, prompter, console)
  ui/
    console.py                  # get_console() singleton Rich
    render.py                   # render_tabela_busca, render_painel_resumo, texto_link_email
    menu.py                     # Menu.registrar()/obter()/itens()
tests/
```

## Autenticação Gmail (OAuth)

- Requer `credentials.json` (tipo `installed`, `redirect_uris=['http://localhost']`) e gera `token.json` na primeira execução via `InstalledAppFlow.run_local_server(port=0, prompt="consent", timeout_seconds=120)`. Lógica em `gaia/core/gmail_auth.py::obter_credenciais()`.
- Escopos: `gmail.readonly` + `gmail.modify` (`SCOPES` em `gmail_auth`). Se mudar escopo, apagar `token.json`.
- `AccessDeniedError` = usuário clicou Cancelar/Negar na tela do Google (não é bug): instruir a clicar **Permitir**; se aparecer "não verificado", `Avançado > Ir para o projeto`.
- `.gitignore` ignora `*.json`: nunca commitar `credentials.json`, `token.json`, `lista_negra.json` nem `resumo_dia_*.json`.

## Fluxo do resumidor (`gaia/routines/resumidor_emails.py::resumir_emails()`)

Orquestra `core/` + `ui/`; não importa `input` direto (recebe `prompter` injetável com default via `input()`). `processar_mensagem()` é testável sem Gmail/rede.

1. Se já existe `resumo_dia_*.json` e é interativo (`perguntar_lista_negra=True`), pergunta `[1] Abrir último [2] Buscar novo` via `escolher_opcao` (default `input()`), **antes** de criar o serviço Gmail. Abrir = mostra `carregar_ultimo_resumo()` **1x1 com `clear`** + `Enter`, sem Gmail/sem marcar lido/sem perguntar blacklist. Sem arquivo ou scheduler (`perguntar_lista_negra=False`) = vai direto ao novo.
1. `core/gmail_client::buscar_dia_mais_recente()` procura o dia mais recente com não lidos, voltando até 30 dias. Filtra só `labelIds=["UNREAD"]` (qualquer caixa, sem `INBOX`). "Hoje" em UTC (`datetime.now(timezone.utc)`). **Só o scheduler** (`perguntar_lista_negra=False`) troca isso por `core/gmail_client::buscar_ultimas_24h()`: `after:<epoch agora-24h>` até agora (janela exata deslizante, atravessa 2 dias de calendário), `dia` gravado = hoje da execução; vazio = avisa `Nenhum ... nas últimas 24 horas` e para (sem cair nos antigos). Manual nunca usa 24h.
2. Gmail `after:` é exclusivo: a query usa `after:<dia anterior> before:<dia seguinte>` para pegar o dia todo.
3. Lista com paginação `nextPageToken`, até 20 páginas (`listar_nao_lidos`).
4. Para cada mensagem: extrai corpo (`text/plain`, ou HTML limpo se `< 50` chars), resume via `core/nlp`, e **marca como lida** via `modify(removeLabelIds=["UNREAD"])` — inclusive bloqueados.
5. Sobrescreve `lista_emails.json` a cada execução (`core/storage::salvar_lista_emails`). Saída final: `resumo_dia_<data-execucao>.json` (`salvar_resumo_dia`) com `{"dia", "resumidos", "ignorados"}` — **soma** no arquivo do dia (mescla anterior + novos, dedup por `id`, `dia` = lote mais recente), nunca apaga o lote anterior do dia.
6. Não há cache de resumos e **não** abrir navegador automaticamente (usuário abre manualmente). O link clicável no terminal usa `https://mail.google.com/mail/u/0/#inbox/<threadId>` (fallback: `id`), via `ui/render::texto_link_email` (`Text` OSC 8).
7. `Scheduler` (A1) em thread daemon dispara `resumir_emails()` às 6h sem bloquear o menu interativo (`perguntar_lista_negra=False`: sempre novo, nunca pergunta abrir/novo); `main()` para o scheduler com `stop()` no `finally` (saída `0`/`Ctrl+C`). Ao concluir com sucesso, marca flag `tem_resumo_pendente()` (limpa em qualquer execução manual); `main::mostrar_banner()` mostra painel `Resumo automático pronto!` até você abrir.

## NLP (`gaia/core/nlp.py::gerar_resumo_extrativo`)

- Resumo extrativo: `sent_tokenize` → `FreqDist` das palavras (sem stopwords) → score `soma(freq)/sqrt(len)` por frase, viés ×1,1 nas 3 primeiras frases → top `N_FRASES_RESUMO = 3` (`gaia/config.py`) frases, na ordem original.
- Idioma: heurística de palavras frequentes, padrão `portuguese`, fallback `english`.
- Corpora NLTK (`punkt_tab`, `punkt`, `stopwords`) baixados automaticamente em `_garantir_recursos_nltk()`.

## Lista negra (`lista_negra.json`) e lista permitida (`lista_permitida.json`, `gaia/core/blacklist.py`)

- Formato: lista de strings — email exato ou domínio (`"@spam.com"`), case-insensitive; remetente extraído de `Nome <email>`.
- Remetente bloqueado: **sem resumo**, marcado como lido e registrado em `ignorados` (lógica em `processar_mensagem` com `esta_bloqueado`).
- Após resumir **todos** e salvar o JSON, fase de resultados **um email por vez com `console.clear()`** (tela sempre “fresco”): `clear` → painel+link → se **remetente novo**, pergunta `Adicionar <email> à lista negra? [s/N]:` via `prompter` na hora; se já está na negra/permitida, espera `Enter` pra avançar (só entre itens, nunca no último — a própria pergunta já pausa o último). Responder `s`: adiciona, salva, move para `ignorados` (não entra em `resumidos`, re-salva o JSON no fim). Responder `N`: adiciona à `lista_permitida.json`, continua em `resumidos` e nunca mais é perguntado (mesmo remetente repetido só é perguntado na 1ª vez: após decidir, entra nas listas e os próximos caem no ramo `Enter`). `por_pagina` vale só pro despejo do scheduler; o manual ignora.
- `Abrir último` é **1x1 com `clear` + `Enter`**, só leitura (sem perguntar blacklist, sem Gmail/marcar lido).
- Scheduler (`main::criar_tarefa_scheduler`) roda com `perguntar_lista_negra=False`: nem pergunta e nem grava nenhuma lista (o `prompt False` automático não conta como decisão).

## Renderização (Rich, `gaia/ui/`)

- Usar `Text("...", style=f"link {url}")` para link clicável (OSC 8). **Não** usar markup `[link url]...[/link]` — quebra com `MarkupError` no Rich 15.
- Escapar strings dinâmicas com `rich.markup.escape` antes de meter em markup.
- `Console` via `ui/console::get_console()` (singleton); banner `pyfiglet` só em `main::mostrar_banner()`, nunca no import.
- `mensagens.json` (~462MB) é legado, não é mais escrito — não carregar/abrir em leitura de teste.

## Regras gerais de desenvolvimento

- Você não pode escrever nenhum código até que tenha escrito um teste de unidade que falhe.
- Você não pode escrever mais de um teste de unidade do que o necessário para falhar (e não compilar é falhar).
- Você não pode escrever mais código do que o suficiente para fazor o teste de unidade que falhou passar.
- Sempre que achar um bug faça um teste que reproduz o bug e que so passa quando o bug não acontecer.
- Novas rotinas: crie em `gaia/routines/`, reutilize `gaia/core/` (escrever 1 vez), apresente via `gaia/ui/`, registre em `main::construir_menu()`. Persistência via `gaia/core/storage.py` (JSON por enquanto).
