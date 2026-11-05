# GAIA

CLI em Python (arquivo único `main.py`) que busca emails não lidos no Gmail, gera resumo extrativo com NLTK e renderiza no terminal com Rich.

## Comandos

```bash
.venv/bin/pip install -r requirements.txt   # deps (nltk, rich, pyfiglet, google-*)
.venv/bin/python main.py                     # menu: 1 = Resumidor de Emails, 0 = sair
```

- Use sempre `.venv/bin/python` (Python 3.12); o `python3` do sistema não tem `nltk`.
- Não há testes, lint ou typecheck configurados. Verificação rápida offline:
  ```bash
  .venv/bin/python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('syntax OK')"
  ```
- `import main` executa o menu (loop `input()` no nível do módulo); para testar funções, `exec` apenas o trecho antes de `opcoes =`.

## Autenticação Gmail (OAuth)

- Requer `credentials.json` (tipo `installed`, `redirect_uris=['http://localhost']`) e gera `token.json` na primeira execução via `InstalledAppFlow.run_local_server(port=0, prompt="consent", timeout_seconds=120)`.
- Escopos: `gmail.readonly` + `gmail.modify`. Se mudar escopo, apagar `token.json`.
- `AccessDeniedError` = usuário clicou Cancelar/Negar na tela do Google (não é bug): instruir a clicar **Permitir**; se aparecer "não verificado", `Avançado > Ir para o projeto`.
- `.gitignore` ignora `*.json`: nunca commitar `credentials.json`, `token.json`, `lista_negra.json` nem `resumo_dia_*.json`.

## Fluxo do resumidor (`resumir_emails()`)

1. Procura o dia mais recente com não lidos, voltando até 30 dias. Filtra só `labelIds=["UNREAD"]` (qualquer caixa, sem `INBOX`).
2. Gmail `after:` é exclusivo: a query usa `after:<dia anterior> before:<dia seguinte>` para pegar o dia todo. "Hoje" é calculado em UTC (`datetime.now(timezone.utc)`).
3. Lista com paginação `nextPageToken`, até 20 páginas (`listar_nao_lidos`).
4. Para cada mensagem: extrai corpo (`text/plain`, ou HTML limpo se `< 50` chars), resume, e **marca como lida** via `modify(removeLabelIds=["UNREAD"])` — inclusive bloqueados.
5. Sobrescreve `lista_emails.json` a cada execução. Saída final: `resumo_dia_<data-execucao>.json` com `{"dia", "resumidos", "ignorados"}`.
6. Não há cache de resumos e **não** abrir navegador automaticamente (usuário abre manualmente). O link clicável no terminal usa `https://mail.google.com/mail/u/0/#inbox/<threadId>` (fallback: `id`).

## NLP (`gerar_resumo_extrativo`)

- Resumo extrativo: `sent_tokenize` → `FreqDist` das palavras (sem stopwords) → score `soma(freq)/sqrt(len)` por frase, viés ×1,1 nas 3 primeiras frases → top `N_FRASES_RESUMO = 3` frases, na ordem original.
- Idioma: heurística de palavras frequentes, padrão `portuguese`, fallback `english`.
- Corpora NLTK (`punkt_tab`, `punkt`, `stopwords`) baixados automaticamente em `_garantir_recursos_nltk()`.

## Lista negra (`lista_negra.json`)

- Formato: lista de strings — email exato ou domínio (`"@spam.com"`), case-insensitive; remetente extraído de `Nome <email>`.
- Remetente bloqueado: **sem resumo**, marcado como lido e registrado em `ignorados`.
- Após renderizar cada resumo, pergunta `Adicionar <email> à lista negra? [s/N]:` **apenas para remetente novo** (quem já está na blacklist nunca é perguntado de novo). Responder `s`: adiciona, salva, marca como lido e move para `ignorados` (não entra em `resumidos`).

## Renderização (Rich)

- Usar `Text("...", style=f"link {url}")` para link clicável (OSC 8). **Não** usar markup `[link url]...[/link]` — quebra com `MarkupError` no Rich 15.
- Escapar strings dinâmicas com `rich.markup.escape` antes de meter em markup.
- `mensagens.json` (~462MB) é legado, não é mais escrito — não carregar/abrir em leitura de teste.

## Regras gerais de desenvolvimento

- Você não pode escrever nenhum código até que tenha escrito um teste de unidade que falhe.
- Você não pode escrever mais de um teste de unidade do que o necessário para falhar (e não compilar é falhar).
- Você não pode escrever mais código do que o suficiente para fazor o teste de unidade que falhou passar.
- Sempre que achar um bug faça um teste que reproduz o bug e que so passa quando o bug não acontecer.
