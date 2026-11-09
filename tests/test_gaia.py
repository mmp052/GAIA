def test_gaia_config_expoe_n_frases():
    from gaia.config import N_FRASES_RESUMO

    assert N_FRASES_RESUMO == 3


def test_blacklist_extrair_email_core():
    from gaia.core.blacklist import extrair_email

    assert extrair_email("João <Joao@EX.com>") == "joao@ex.com"


def test_blacklist_esta_bloqueado_dominio_core():
    from gaia.core.blacklist import esta_bloqueado

    assert esta_bloqueado("User <User@SPAM.com>", ["@spam.com"]) is True


def test_blacklist_salvar_carregar_core(tmp_path, monkeypatch):
    from gaia.core.blacklist import carregar_lista_negra, salvar_lista_negra

    monkeypatch.chdir(tmp_path)
    salvar_lista_negra(["a@b.com"])
    assert carregar_lista_negra() == ["a@b.com"]


def test_lista_permitida_salvar_carregar_esta_permitido(tmp_path, monkeypatch):
    from gaia.core.blacklist import carregar_lista_permitida, esta_permitido, salvar_lista_permitida

    monkeypatch.chdir(tmp_path)
    salvar_lista_permitida(["a@b.com"])
    assert carregar_lista_permitida() == ["a@b.com"]
    assert esta_permitido("A <a@b.com>", ["a@b.com"]) is True
    assert esta_permitido("B <b@c.com>", ["a@b.com"]) is False


def test_email_extract_header_core():
    from gaia.core.email_extract import extrair_texto_email, obter_header

    payload = {"headers": [{"name": "From", "value": "a@b.com"}]}
    assert obter_header(payload, "from") == "a@b.com"
    import base64

    msg = {"payload": {"mimeType": "text/plain", "body": {"data": base64.urlsafe_b64encode("Olá mundo, este é um email bem longo para teste.".encode()).decode()}}}
    assert "Olá" in extrair_texto_email(msg)


def test_nlp_resumo_curto_core():
    from gaia.core.nlp import detectar_idioma, gerar_resumo_extrativo

    assert detectar_idioma("Olá, você é de que lugar? Obrigado.") == "portuguese"
    resumo, _ = gerar_resumo_extrativo("curto")
    assert resumo == "curto"


def test_storage_salva_resumo_core(tmp_path, monkeypatch):
    from gaia.core.storage import salvar_resumo_dia

    monkeypatch.chdir(tmp_path)
    nome = salvar_resumo_dia("2026/11/05", [{"id": "1"}], [{"id": "2"}])
    import json

    dados = json.loads((tmp_path / nome).read_text(encoding="utf-8"))
    assert dados["dia"] == "2026/11/05"
    assert dados["resumidos"][0]["id"] == "1"


def test_storage_salva_resumo_mescla_sem_duplicar(tmp_path, monkeypatch):
    import json
    from datetime import datetime

    from gaia.core.storage import salvar_resumo_dia

    monkeypatch.chdir(tmp_path)
    agora = datetime(2026, 11, 9, 6, 0)
    salvar_resumo_dia("2026/11/08", [{"id": "1"}, {"id": "2"}], [{"id": "9"}], agora=agora)
    nome = salvar_resumo_dia("2026/11/09", [{"id": "2"}, {"id": "3"}], [{"id": "10"}], agora=agora)
    dados = json.loads((tmp_path / nome).read_text(encoding="utf-8"))
    assert [r["id"] for r in dados["resumidos"]] == ["1", "2", "3"]
    assert [r["id"] for r in dados["ignorados"]] == ["9", "10"]
    assert dados["dia"] == "2026/11/09"


def test_storage_carrega_ultimo_resumo(tmp_path, monkeypatch):
    import json

    from gaia.core.storage import carregar_ultimo_resumo

    monkeypatch.chdir(tmp_path)
    assert carregar_ultimo_resumo() is None
    (tmp_path / "resumo_dia_2026-11-08.json").write_text(json.dumps({"dia": "2026/11/08", "resumidos": [{"id": "1"}], "ignorados": []}), encoding="utf-8")
    (tmp_path / "resumo_dia_2026-11-09.json").write_text(json.dumps({"dia": "2026/11/09", "resumidos": [{"id": "2"}], "ignorados": [{"id": "3"}]}), encoding="utf-8")
    ultimo = carregar_ultimo_resumo()
    assert ultimo["arquivo"] == "resumo_dia_2026-11-09.json"
    assert ultimo["dia"] == "2026/11/09"
    assert [r["id"] for r in ultimo["resumidos"]] == ["2"]


def test_gmail_client_listar_paginacao_core():
    from gaia.core.gmail_client import listar_nao_lidos

    class FakeMessages:
        def __init__(self):
            self.calls = 0

        def list(self, **params):
            self.calls += 1

            class R:
                def __init__(self, msgs, token):
                    self.msgs = msgs
                    self.token = token

                def execute(self):
                    return {"messages": self.msgs, **({"nextPageToken": self.token} if self.token else {})}

            if self.calls == 1:
                return R([{"id": "1"}], "tok")
            return R([{"id": "2"}], None)

    class FakeUsersMessages:
        def __init__(self, inner):
            self.inner = inner

        # service.users().messages() encadeado
        pass

    class FakeService:
        def __init__(self):
            self._messages = FakeMessages()

            class Users:
                def __init__(self, outer):
                    self.outer = outer

                def messages(self):
                    return self.outer._messages

            self._users = Users(self)

        def users(self):
            return self._users

    svc = FakeService()
    resultado = listar_nao_lidos(svc, "q-teste")
    assert resultado == [{"id": "1"}, {"id": "2"}]


def test_gmail_auth_scopes_core():
    from gaia.core.gmail_auth import SCOPES

    assert any("gmail.readonly" in s for s in SCOPES)
    assert any("gmail.modify" in s for s in SCOPES)


def test_ui_console_unico():
    from gaia.ui.console import get_console

    c1 = get_console()
    c2 = get_console()
    assert c1 is c2


def test_ui_render_link():
    from gaia.ui.render import texto_link_email

    txt = texto_link_email("https://mail.google.com/mail/u/0/#inbox/thread1")
    # Text com estilo link (OSC 8) deve conter o texto
    assert txt.plain == "▶ Ler email completo"


def test_ui_menu_registra_rotina():
    from gaia.ui.menu import Menu

    menu = Menu()
    menu.registrar("1", "Resumidor de Emails", lambda: "ok")
    assert menu.obter("1")() == "ok"


def test_scheduler_nao_dispara_antes_das_6h():
    from gaia.scheduler import deve_disparar

    assert deve_disparar(agora_hora=(5, 59), ultima_execucao=None) is False
    assert deve_disparar(agora_hora=(6, 0), ultima_execucao=None) is True


def test_scheduler_nao_dispara_fora_do_horario_6h():
    from gaia.scheduler import deve_disparar

    assert deve_disparar(agora_hora=(20, 51), ultima_execucao=None) is False


def test_resumidor_bloqueado_ignora_sem_resumo():
    from gaia.routines.resumidor_emails import processar_mensagem

    resultado = processar_mensagem(
        msg_id="1",
        msg={"payload": {"headers": [{"name": "From", "value": "spam@x.com"}]}},
        lista_negra=["@x.com"],
        prompter=lambda email: False,
        resumo_fn=lambda texto: ("r", "portuguese"),
    )
    assert resultado["ignorado"] is True
    assert "resumo" not in resultado


def test_processar_mensagem_nao_chama_prompter_no_resumo():
    import base64

    from gaia.routines.resumidor_emails import processar_mensagem

    def prompter_proibido(email):
        raise AssertionError(f"prompter não deveria ser chamado durante o resumo: {email}")

    msg = {
        "payload": {
            "headers": [{"name": "From", "value": "Novo <novo@ex.com>"}, {"name": "Subject", "value": "Oi"}, {"name": "Date", "value": "D"}],
            "mimeType": "text/plain",
            "body": {"data": base64.urlsafe_b64encode(b"Texto longo para resumo de verdade um dois tres.").decode()},
        },
        "threadId": "t1",
    }
    resultado = processar_mensagem(
        msg_id="1",
        msg=msg,
        lista_negra=[],
        prompter=prompter_proibido,
        resumo_fn=lambda texto, n_frases=3: ("r", "portuguese"),
    )
    assert resultado["ignorado"] is False
    assert resultado["resumo"] == "r"


def test_main_import_silencioso():
    import subprocess
    import sys
    from pathlib import Path

    resultado = subprocess.run(
        [sys.executable, "-c", "import main"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "GAIA" not in resultado.stdout
    assert "Digite a opção" not in resultado.stdout


def test_gmail_client_buscar_chama_on_progress():
    from datetime import date

    from gaia.core.gmail_client import buscar_dia_mais_recente

    class FakeMessages:
        def list(self, **params):
            class R:
                def execute(self):
                    return {"messages": [{"id": "1"}]}

            return R()

    class FakeService:
        def __init__(self):
            outer = self

            class Users:
                def messages(self):
                    return FakeMessages()

            self._users = Users()

        def users(self):
            return self._users

    chamadas = []
    buscar_dia_mais_recente(
        FakeService(),
        date(2026, 11, 8),
        dias=3,
        on_progress=lambda dia_str, qtd, atual, total: chamadas.append((dia_str, qtd, atual, total)),
    )
    assert chamadas and chamadas[0][0] == "2026/11/08"
    assert chamadas[0][1] == 1


def test_gmail_client_buscar_ultimas_24h_usa_epoch():
    from datetime import datetime, timezone

    from gaia.core.gmail_client import buscar_ultimas_24h

    consultas = []

    class FakeMessages:
        def list(self, **params):
            consultas.append(params.get("q"))

            class R:
                def execute(self):
                    return {"messages": [{"id": "1"}]}

            return R()

    class FakeService:
        def __init__(self):
            class Users:
                def messages(self):
                    return FakeMessages()

            self._users = Users()

        def users(self):
            return self._users

    agora = datetime(2026, 11, 9, 6, 0, tzinfo=timezone.utc)
    data_alvo, lista, busca = buscar_ultimas_24h(FakeService(), agora)
    epoch = int(datetime(2026, 11, 8, 6, 0, tzinfo=timezone.utc).timestamp())
    assert consultas == [f"after:{epoch}"]
    assert data_alvo == "2026/11/09"
    assert [m["id"] for m in lista] == ["1"]
    assert busca == [("2026/11/09", 1)]


def test_ui_progress_tem_spinner_e_barra():
    from rich.progress import BarColumn, Progress, SpinnerColumn

    from gaia.ui.progress import criar_progress

    import io
    from rich.console import Console

    console = Console(file=io.StringIO())
    progress = criar_progress(console)
    assert isinstance(progress, Progress)
    colunas = [type(c) for c in progress.columns]
    assert SpinnerColumn in colunas
    assert BarColumn in colunas


def test_ui_exibir_traceback_mostra_erro():
    import io

    from rich.console import Console

    from gaia.ui.erros import exibir_traceback

    arquivo = io.StringIO()
    console = Console(file=arquivo, force_terminal=False, width=200)
    try:
        raise ValueError("boom-teste")
    except ValueError as exc:
        exibir_traceback(console, exc, contexto="processar email 2")
    saida = arquivo.getvalue()
    assert "boom-teste" in saida
    assert "Traceback" in saida


def test_ui_exibir_paginado_pagina_de_5_em_5():
    import io

    from rich.console import Console

    from gaia.ui.screens import exibir_paginado

    arquivo = io.StringIO()
    console = Console(file=arquivo, force_terminal=False, width=200)
    chamadas = []

    def entrada_falsa(prompt=""):
        chamadas.append(prompt)
        arquivo.write(f"ENTER:{prompt}\n")
        return ""

    exibir_paginado(
        console,
        [f"email-{i}" for i in range(7)],
        por_pagina=5,
        entrada=entrada_falsa,
    )
    saida = arquivo.getvalue()
    assert "email-0" in saida and "email-6" in saida
    assert len(chamadas) == 1


def test_ui_telas_limpam_ao_trocar():
    class ConsoleFalso:
        def __init__(self):
            self.limpezas = 0
            self.impressos = []

        def clear(self):
            self.limpezas += 1

        def print(self, *a, **k):
            self.impressos.append(a)

    from gaia.ui.menu import Menu
    from gaia.ui.screens import exibir_cabecalho_rotina, exibir_menu

    console = ConsoleFalso()
    menu = Menu()
    menu.registrar("1", "Resumidor de Emails", lambda: "ok")
    exibir_menu(console, menu)
    assert console.limpezas == 1
    exibir_cabecalho_rotina(console, "Resumidor de Emails")
    assert console.limpezas == 2


def test_resumidor_para_e_mostra_traceback_no_erro(tmp_path, monkeypatch):
    import base64
    import io

    import pytest

    from rich.console import Console

    from gaia.routines import resumidor_emails

    monkeypatch.chdir(tmp_path)

    b64 = lambda t: base64.urlsafe_b64encode(t.encode()).decode()
    msgs = {
        "1": {"payload": {"headers": [{"name": "From", "value": "a@b.com"}, {"name": "Subject", "value": "S1"}, {"name": "Date", "value": "D"}], "mimeType": "text/plain", "body": {"data": b64("Ola mundo texto longo para resumo de verdade um dois tres.")}}, "threadId": "t1"},
        "3": {"payload": {"headers": [{"name": "From", "value": "c@d.com"}, {"name": "Subject", "value": "S3"}, {"name": "Date", "value": "D"}], "mimeType": "text/plain", "body": {"data": b64("Ola mundo texto longo para resumo de verdade um dois tres.")}}, "threadId": "t3"},
    }

    class FakeMessages:
        def list(self, **p):
            class R:
                def execute(self):
                    return {"messages": [{"id": "1"}, {"id": "2"}, {"id": "3"}]}

            return R()

        def get(self, userId=None, id=None):
            outer = self

            class R:
                def execute(_):
                    if id == "2":
                        raise RuntimeError("boom-get-2")
                    return msgs[id]

            return R()

        def modify(self, **p):
            class R:
                def execute(self):
                    return {}

            return R()

    class FakeService:
        def __init__(self):
            outer = self

            class Users:
                def messages(self):
                    return FakeMessages()

            self._users = Users()

        def users(self):
            return self._users

    monkeypatch.setattr(resumidor_emails, "gerar_resumo_extrativo", lambda texto, n_frases=3: ("r", "portuguese"))
    console = Console(file=io.StringIO(), force_terminal=False, width=200)
    with pytest.raises(RuntimeError, match="boom-get-2"):
        resumidor_emails.resumir_emails(
            service=FakeService(),
            prompter=lambda email: False,
            console=console,
            pager_input=lambda prompt="": "",
            por_pagina=5,
        )


def test_resumidor_nao_roda_duas_vezes_concorrentes(tmp_path, monkeypatch):
    import io

    from rich.console import Console

    from gaia.routines import resumidor_emails

    monkeypatch.chdir(tmp_path)
    chamado = []

    class FakeService:
        def users(self):
            chamado.append(1)
            raise AssertionError("service não deveria ser chamado com lock preso")

    resumidor_emails._execucao_lock.acquire()
    try:
        console = Console(file=io.StringIO(), force_terminal=False, width=200)
        resultado = resumidor_emails.resumir_emails(
            service=FakeService(),
            prompter=lambda email: False,
            console=console,
            pager_input=lambda prompt="": "",
        )
        assert resultado["dia"] is None
        assert chamado == []
    finally:
        resumidor_emails._execucao_lock.release()


def test_main_tarefa_scheduler_nao_chama_input(monkeypatch):
    import main as gaia_main

    chamadas = {}

    def fake_impl(**kwargs):
        chamadas.update(kwargs)
        return {"dia": None}

    monkeypatch.setattr(gaia_main, "_resumir_emails_impl", fake_impl)
    tarefa = gaia_main.criar_tarefa_scheduler()
    # não deve chamar input nem ler stdin
    tarefa()
    assert chamadas["prompter"]("spam@x.com") is False
    assert chamadas["pager_input"]("irrelevant") == ""


def test_scheduler_exibe_traceback_em_erro(capsys):
    from gaia.scheduler import executar_com_traceback

    def tarefa_falha():
        raise RuntimeError("boom-scheduler")

    executar_com_traceback(tarefa_falha)
    capturado = capsys.readouterr()
    saida = capturado.out + capturado.err
    assert "boom-scheduler" in saida
    assert "Traceback" in saida


def test_main_executar_rotina_mostra_traceback_e_continua():
    import io

    from rich.console import Console

    import main as gaia_main

    arquivo = io.StringIO()
    console = Console(file=arquivo, force_terminal=False, width=200)

    def funcao_falha():
        raise ValueError("boom-rotina")

    gaia_main.executar_rotina(funcao_falha, "Resumidor de Emails", console=console)
    saida = arquivo.getvalue()
    assert "boom-rotina" in saida
    assert "Traceback" in saida


def test_resumidor_pergunta_lista_negra_apos_resumir_tudo(tmp_path, monkeypatch):
    import base64
    import io
    import json

    from rich.console import Console

    from gaia.routines import resumidor_emails

    monkeypatch.chdir(tmp_path)

    b64 = lambda t: base64.urlsafe_b64encode(t.encode()).decode()
    ordem = []
    msgs = {
        "1": {"payload": {"headers": [{"name": "From", "value": "Novo <novo@ex.com>"}, {"name": "Subject", "value": "S1"}, {"name": "Date", "value": "D"}], "mimeType": "text/plain", "body": {"data": b64("Texto longo para resumo de verdade um dois tres quatro.")}}, "threadId": "t1"},
        "2": {"payload": {"headers": [{"name": "From", "value": "Outro <outro@ex.com>"}, {"name": "Subject", "value": "S2"}, {"name": "Date", "value": "D"}], "mimeType": "text/plain", "body": {"data": b64("Outro texto longo para resumo de verdade um dois.")}}, "threadId": "t2"},
    }

    class FakeMessages:
        def list(self, **p):
            class R:
                def execute(self):
                    return {"messages": [{"id": "1"}, {"id": "2"}]}

            return R()

        def get(self, userId=None, id=None):
            ordem.append(f"get-{id}")

            class R:
                def execute(_):
                    return msgs[id]

            return R()

        def modify(self, **p):
            class R:
                def execute(self):
                    return {}

            return R()

    class FakeService:
        def __init__(self):
            class Users:
                def messages(self):
                    return FakeMessages()

            self._users = Users()

        def users(self):
            return self._users

    def prompter(email):
        ordem.append(f"prompt-{email}")
        # ao perguntar, os 2 gets já aconteceram e o JSON inicial já tem 2 resumidos
        assert ordem.count("get-1") == 1 and ordem.count("get-2") == 1
        arquivos = list(tmp_path.glob("resumo_dia_*.json"))
        assert arquivos, "JSON deveria existir antes de perguntar"
        dados = json.loads(arquivos[0].read_text(encoding="utf-8"))
        assert len(dados["resumidos"]) == 2
        return email == "novo@ex.com"

    monkeypatch.setattr(resumidor_emails, "gerar_resumo_extrativo", lambda texto, n_frases=3: ("r", "portuguese"))
    console = Console(file=io.StringIO(), force_terminal=False, width=200)
    resultado = resumidor_emails.resumir_emails(
        service=FakeService(),
        prompter=prompter,
        console=console,
        pager_input=lambda prompt="": "",
        por_pagina=5,
    )
    assert {r["id"] for r in resultado["resumidos"]} == {"2"}
    assert {i["id"] for i in resultado["ignorados"]} == {"1"}
    assert ordem.index("prompt-novo@ex.com") > ordem.index("get-2")


def test_resumidor_salva_nao_na_lista_permitida_e_nao_pergunta_de_novo(tmp_path, monkeypatch):
    import base64
    import io
    import json

    from rich.console import Console

    from gaia.routines import resumidor_emails

    monkeypatch.chdir(tmp_path)

    b64 = lambda t: base64.urlsafe_b64encode(t.encode()).decode()
    msgs = {
        "1": {"payload": {"headers": [{"name": "From", "value": "Novo <novo@ex.com>"}, {"name": "Subject", "value": "S1"}, {"name": "Date", "value": "D"}], "mimeType": "text/plain", "body": {"data": b64("Texto longo para resumo de verdade um dois tres quatro.")}}, "threadId": "t1"},
        "2": {"payload": {"headers": [{"name": "From", "value": "Outro <outro@ex.com>"}, {"name": "Subject", "value": "S2"}, {"name": "Date", "value": "D"}], "mimeType": "text/plain", "body": {"data": b64("Outro texto longo para resumo de verdade um dois.")}}, "threadId": "t2"},
    }

    class FakeMessages:
        def list(self, **p):
            class R:
                def execute(self):
                    return {"messages": [{"id": "1"}, {"id": "2"}]}

            return R()

        def get(self, userId=None, id=None):
            class R:
                def execute(_):
                    return msgs[id]

            return R()

        def modify(self, **p):
            class R:
                def execute(self):
                    return {}

            return R()

    class FakeService:
        def __init__(self):
            class Users:
                def messages(self):
                    return FakeMessages()

            self._users = Users()

        def users(self):
            return self._users

    monkeypatch.setattr(resumidor_emails, "gerar_resumo_extrativo", lambda texto, n_frases=3: ("r", "portuguese"))

    def rodar(prompter):
        console = Console(file=io.StringIO(), force_terminal=False, width=200)
        return resumidor_emails.resumir_emails(
            service=FakeService(),
            prompter=prompter,
            console=console,
            pager_input=lambda prompt="": "",
            por_pagina=5,
            escolher_opcao=lambda: "novo",
        )

    resultado1 = rodar(lambda email: email == "novo@ex.com")
    assert {r["id"] for r in resultado1["resumidos"]} == {"2"}
    assert json.loads((tmp_path / "lista_negra.json").read_text(encoding="utf-8")) == ["novo@ex.com"]
    assert json.loads((tmp_path / "lista_permitida.json").read_text(encoding="utf-8")) == ["outro@ex.com"]

    def prompter_proibido(email):
        raise AssertionError(f"não deveria perguntar de novo: {email}")

    resultado2 = rodar(prompter_proibido)
    assert {r["id"] for r in resultado2["resumidos"]} == {"2"}
    assert {i["id"] for i in resultado2["ignorados"]} == {"1"}


def test_resumidor_sem_pergunta_nao_grava_listas(tmp_path, monkeypatch):
    import base64
    import io

    from rich.console import Console

    from gaia.routines import resumidor_emails

    monkeypatch.chdir(tmp_path)

    b64 = lambda t: base64.urlsafe_b64encode(t.encode()).decode()
    msgs = {
        "1": {"payload": {"headers": [{"name": "From", "value": "Novo <novo@ex.com>"}, {"name": "Subject", "value": "S1"}, {"name": "Date", "value": "D"}], "mimeType": "text/plain", "body": {"data": b64("Texto longo para resumo de verdade um dois tres quatro.")}}, "threadId": "t1"},
    }

    class FakeMessages:
        def list(self, **p):
            class R:
                def execute(self):
                    return {"messages": [{"id": "1"}]}

            return R()

        def get(self, userId=None, id=None):
            class R:
                def execute(_):
                    return msgs[id]

            return R()

        def modify(self, **p):
            class R:
                def execute(self):
                    return {}

            return R()

    class FakeService:
        def __init__(self):
            class Users:
                def messages(self):
                    return FakeMessages()

            self._users = Users()

        def users(self):
            return self._users

    monkeypatch.setattr(resumidor_emails, "gerar_resumo_extrativo", lambda texto, n_frases=3: ("r", "portuguese"))

    def prompter_proibido(email):
        raise AssertionError(f"scheduler não deveria perguntar: {email}")

    console = Console(file=io.StringIO(), force_terminal=False, width=200)
    resultado = resumidor_emails.resumir_emails(
        service=FakeService(),
        prompter=prompter_proibido,
        console=console,
        pager_input=lambda prompt="": "",
        perguntar_lista_negra=False,
    )
    assert {r["id"] for r in resultado["resumidos"]} == {"1"}
    assert not (tmp_path / "lista_negra.json").exists()
    assert not (tmp_path / "lista_permitida.json").exists()


def test_resumidor_abrir_ultimo_nao_chama_gmail(tmp_path, monkeypatch):
    import io
    import json

    from rich.console import Console

    from gaia.routines import resumidor_emails

    monkeypatch.chdir(tmp_path)
    (tmp_path / "resumo_dia_2026-11-09.json").write_text(
        json.dumps(
            {
                "dia": "2026/11/09",
                "resumidos": [
                    {"id": "1", "de": "A <a@b.com>", "assunto": "Oi", "data": "D", "resumo": "Resumo velho", "idioma": "portuguese", "link_email": "https://x/1"},
                    {"id": "2", "de": "B <b@b.com>", "assunto": "Oi2", "data": "D", "resumo": "Outro resumo", "idioma": "portuguese", "link_email": "https://x/2"},
                ],
                "ignorados": [{"id": "9", "de": "S <s@b.com>", "assunto": "S", "data": "D"}],
            }
        ),
        encoding="utf-8",
    )

    class FakeService:
        def users(self):
            raise AssertionError("abrir último não deveria chamar o Gmail")

    arquivo = io.StringIO()
    console = Console(file=arquivo, force_terminal=False, width=200)
    resultado = resumidor_emails.resumir_emails(
        service=FakeService(),
        escolher_opcao=lambda: "abrir",
        console=console,
        pager_input=lambda prompt="": "",
        por_pagina=5,
    )
    assert resultado["dia"] == "2026/11/09"
    assert [r["id"] for r in resultado["resumidos"]] == ["1", "2"]
    assert resultado["arquivo"] == "resumo_dia_2026-11-09.json"
    saida = arquivo.getvalue()
    assert "Resumo velho" in saida and "Outro resumo" in saida


def test_resumidor_scheduler_ignora_pergunta_e_busca_novo(tmp_path, monkeypatch):
    import base64
    import io
    import json

    from rich.console import Console

    from gaia.routines import resumidor_emails

    monkeypatch.chdir(tmp_path)
    from datetime import datetime

    hoje = datetime.now().strftime("%Y-%m-%d")
    (tmp_path / f"resumo_dia_{hoje}.json").write_text(json.dumps({"dia": hoje, "resumidos": [{"id": "99", "de": "A <a@b.com>", "assunto": "V", "data": "D", "resumo": "Velho", "idioma": "portuguese", "link_email": "https://x/99"}], "ignorados": []}), encoding="utf-8")

    b64 = lambda t: base64.urlsafe_b64encode(t.encode()).decode()
    msgs = {"1": {"payload": {"headers": [{"name": "From", "value": "Novo <novo@ex.com>"}, {"name": "Subject", "value": "S1"}, {"name": "Date", "value": "D"}], "mimeType": "text/plain", "body": {"data": b64("Texto longo para resumo de verdade um dois tres quatro.")}}, "threadId": "t1"}}

    class FakeMessages:
        def list(self, **p):
            class R:
                def execute(self):
                    return {"messages": [{"id": "1"}]}

            return R()

        def get(self, userId=None, id=None):
            class R:
                def execute(_):
                    return msgs[id]

            return R()

        def modify(self, **p):
            class R:
                def execute(self):
                    return {}

            return R()

    class FakeService:
        def __init__(self):
            class Users:
                def messages(self):
                    return FakeMessages()

            self._users = Users()

        def users(self):
            return self._users

    monkeypatch.setattr(resumidor_emails, "gerar_resumo_extrativo", lambda texto, n_frases=3: ("r", "portuguese"))

    def escolher_proibido():
        raise AssertionError("scheduler não deveria perguntar abrir/novo")

    console = Console(file=io.StringIO(), force_terminal=False, width=200)
    resultado = resumidor_emails.resumir_emails(
        service=FakeService(),
        escolher_opcao=escolher_proibido,
        prompter=lambda email: False,
        console=console,
        pager_input=lambda prompt="": "",
        perguntar_lista_negra=False,
    )
    assert {r["id"] for r in resultado["resumidos"]} == {"1"}
    # arquivo do dia somou o antigo (99) + o novo (1)
    dados = json.loads((tmp_path / resultado["arquivo"]).read_text(encoding="utf-8"))
    assert {r["id"] for r in dados["resumidos"]} == {"99", "1"}


def test_banner_pendente_scheduler_marca_e_abrir_limpa(tmp_path, monkeypatch):
    import base64
    import io

    from rich.console import Console

    from gaia.routines import resumidor_emails

    monkeypatch.chdir(tmp_path)
    resumidor_emails.limpar_resumo_pendente()
    assert resumidor_emails.tem_resumo_pendente() is False

    b64 = lambda t: base64.urlsafe_b64encode(t.encode()).decode()
    msgs = {"1": {"payload": {"headers": [{"name": "From", "value": "Novo <novo@ex.com>"}, {"name": "Subject", "value": "S1"}, {"name": "Date", "value": "D"}], "mimeType": "text/plain", "body": {"data": b64("Texto longo para resumo de verdade um dois tres quatro.")}}, "threadId": "t1"}}

    class FakeMessages:
        def list(self, **p):
            class R:
                def execute(self):
                    return {"messages": [{"id": "1"}]}

            return R()

        def get(self, userId=None, id=None):
            class R:
                def execute(_):
                    return msgs[id]

            return R()

        def modify(self, **p):
            class R:
                def execute(self):
                    return {}

            return R()

    class FakeService:
        def __init__(self):
            class Users:
                def messages(self):
                    return FakeMessages()

            self._users = Users()

        def users(self):
            return self._users

    monkeypatch.setattr(resumidor_emails, "gerar_resumo_extrativo", lambda texto, n_frases=3: ("r", "portuguese"))
    console = Console(file=io.StringIO(), force_terminal=False, width=200)
    resumidor_emails.resumir_emails(service=FakeService(), prompter=lambda e: False, console=console, pager_input=lambda prompt="": "", perguntar_lista_negra=False)
    assert resumidor_emails.tem_resumo_pendente() is True

    class FakeServiceFechado:
        def users(self):
            raise AssertionError("abrir não chama Gmail")

    console2 = Console(file=io.StringIO(), force_terminal=False, width=200)
    resumidor_emails.resumir_emails(service=FakeServiceFechado(), escolher_opcao=lambda: "abrir", console=console2, pager_input=lambda prompt="": "")
    assert resumidor_emails.tem_resumo_pendente() is False


def test_main_mostrar_banner_avisa_resumo_pendente():
    import io

    from rich.console import Console

    import main as gaia_main
    from gaia.routines import resumidor_emails

    resumidor_emails.marcar_resumo_pendente()
    try:
        arquivo = io.StringIO()
        console = Console(file=arquivo, force_terminal=False, width=200)
        gaia_main.mostrar_banner(console)
        saida = arquivo.getvalue()
        assert "Resumo automático" in saida
        assert "Abrir último" in saida
    finally:
        resumidor_emails.limpar_resumo_pendente()

    arquivo2 = io.StringIO()
    console2 = Console(file=arquivo2, force_terminal=False, width=200)
    gaia_main.mostrar_banner(console2)
    assert "Resumo automático" not in arquivo2.getvalue()


def test_resumidor_mostra_um_email_por_vez_com_clear_e_pergunta(tmp_path, monkeypatch):
    import base64
    import io

    from rich.console import Console

    from gaia.routines import resumidor_emails

    monkeypatch.chdir(tmp_path)

    b64 = lambda t: base64.urlsafe_b64encode(t.encode()).decode()
    msgs = {
        "1": {"payload": {"headers": [{"name": "From", "value": "Novo <novo@ex.com>"}, {"name": "Subject", "value": "S1"}, {"name": "Date", "value": "D"}], "mimeType": "text/plain", "body": {"data": b64("Texto longo para resumo de verdade um dois tres quatro.")}}, "threadId": "t1"},
        "2": {"payload": {"headers": [{"name": "From", "value": "Outro <outro@ex.com>"}, {"name": "Subject", "value": "S2"}, {"name": "Date", "value": "D"}], "mimeType": "text/plain", "body": {"data": b64("Outro texto longo para resumo de verdade um dois.")}}, "threadId": "t2"},
    }

    class FakeMessages:
        def list(self, **p):
            class R:
                def execute(self):
                    return {"messages": [{"id": "1"}, {"id": "2"}]}

            return R()

        def get(self, userId=None, id=None):
            class R:
                def execute(_):
                    return msgs[id]

            return R()

        def modify(self, **p):
            class R:
                def execute(self):
                    return {}

            return R()

    class FakeService:
        def __init__(self):
            class Users:
                def messages(self):
                    return FakeMessages()

            self._users = Users()

        def users(self):
            return self._users

    monkeypatch.setattr(resumidor_emails, "gerar_resumo_extrativo", lambda texto, n_frases=3: ("r", "portuguese"))
    eventos = []
    console = Console(file=io.StringIO(), force_terminal=False, width=200)
    console.clear = lambda: eventos.append("clear")

    def prompter(email):
        eventos.append(f"prompt-{email}")
        return email == "novo@ex.com"

    def pager(prompt=""):
        eventos.append("enter")
        return ""

    resultado = resumidor_emails.resumir_emails(
        service=FakeService(),
        prompter=prompter,
        console=console,
        pager_input=pager,
        por_pagina=5,
        escolher_opcao=lambda: "novo",
    )
    assert eventos == ["clear", "prompt-novo@ex.com", "clear", "prompt-outro@ex.com"]
    assert {r["id"] for r in resultado["resumidos"]} == {"2"}
    assert {i["id"] for i in resultado["ignorados"]} == {"1"}


def test_resumidor_remetente_conhecido_avanca_com_enter_sem_perguntar(tmp_path, monkeypatch):
    import base64
    import io
    import json

    from rich.console import Console

    from gaia.routines import resumidor_emails

    monkeypatch.chdir(tmp_path)
    (tmp_path / "lista_permitida.json").write_text(json.dumps(["a@b.com", "c@d.com"]), encoding="utf-8")

    b64 = lambda t: base64.urlsafe_b64encode(t.encode()).decode()
    msgs = {
        "1": {"payload": {"headers": [{"name": "From", "value": "A <a@b.com>"}, {"name": "Subject", "value": "S1"}, {"name": "Date", "value": "D"}], "mimeType": "text/plain", "body": {"data": b64("Texto longo para resumo de verdade um dois tres quatro.")}}, "threadId": "t1"},
        "2": {"payload": {"headers": [{"name": "From", "value": "C <c@d.com>"}, {"name": "Subject", "value": "S2"}, {"name": "Date", "value": "D"}], "mimeType": "text/plain", "body": {"data": b64("Outro texto longo para resumo de verdade um dois.")}}, "threadId": "t2"},
    }

    class FakeMessages:
        def list(self, **p):
            class R:
                def execute(self):
                    return {"messages": [{"id": "1"}, {"id": "2"}]}

            return R()

        def get(self, userId=None, id=None):
            class R:
                def execute(_):
                    return msgs[id]

            return R()

        def modify(self, **p):
            class R:
                def execute(self):
                    return {}

            return R()

    class FakeService:
        def __init__(self):
            class Users:
                def messages(self):
                    return FakeMessages()

            self._users = Users()

        def users(self):
            return self._users

    monkeypatch.setattr(resumidor_emails, "gerar_resumo_extrativo", lambda texto, n_frases=3: ("r", "portuguese"))
    eventos = []
    console = Console(file=io.StringIO(), force_terminal=False, width=200)
    console.clear = lambda: eventos.append("clear")

    def prompter_proibido(email):
        raise AssertionError(f"não deveria perguntar conhecido: {email}")

    def pager(prompt=""):
        eventos.append("enter")
        return ""

    resultado = resumidor_emails.resumir_emails(
        service=FakeService(),
        prompter=prompter_proibido,
        console=console,
        pager_input=pager,
        por_pagina=5,
        escolher_opcao=lambda: "novo",
    )
    assert eventos == ["clear", "enter", "clear"]
    assert {r["id"] for r in resultado["resumidos"]} == {"1", "2"}


def test_resumidor_abrir_ultimo_um_a_um_com_clear(tmp_path, monkeypatch):
    import io
    import json

    from rich.console import Console

    from gaia.routines import resumidor_emails

    monkeypatch.chdir(tmp_path)
    (tmp_path / "resumo_dia_2026-11-09.json").write_text(
        json.dumps(
            {
                "dia": "2026/11/09",
                "resumidos": [
                    {"id": "1", "de": "A <a@b.com>", "assunto": "Oi", "data": "D", "resumo": "Resumo velho", "idioma": "portuguese", "link_email": "https://x/1"},
                    {"id": "2", "de": "B <b@b.com>", "assunto": "Oi2", "data": "D", "resumo": "Outro resumo", "idioma": "portuguese", "link_email": "https://x/2"},
                ],
                "ignorados": [],
            }
        ),
        encoding="utf-8",
    )

    eventos = []
    console = Console(file=io.StringIO(), force_terminal=False, width=200)
    console.clear = lambda: eventos.append("clear")

    def pager(prompt=""):
        eventos.append("enter")
        return ""

    def prompter_proibido(email):
        raise AssertionError("abrir último não pergunta lista negra")

    resultado = resumidor_emails.resumir_emails(
        service=object(),
        escolher_opcao=lambda: "abrir",
        prompter=prompter_proibido,
        console=console,
        pager_input=pager,
        por_pagina=5,
    )
    assert eventos == ["clear", "enter", "clear"]
    assert [r["id"] for r in resultado["resumidos"]] == ["1", "2"]


def test_resumidor_scheduler_busca_ultimas_24h(tmp_path, monkeypatch):
    import base64
    import io
    from datetime import datetime, timezone

    from rich.console import Console

    from gaia.routines import resumidor_emails

    monkeypatch.chdir(tmp_path)
    consultas = []

    b64 = lambda t: base64.urlsafe_b64encode(t.encode()).decode()
    msgs = {"1": {"payload": {"headers": [{"name": "From", "value": "Novo <novo@ex.com>"}, {"name": "Subject", "value": "S1"}, {"name": "Date", "value": "D"}], "mimeType": "text/plain", "body": {"data": b64("Texto longo para resumo de verdade um dois tres quatro.")}}, "threadId": "t1"}}

    class FakeMessages:
        def list(self, **p):
            consultas.append(p.get("q", ""))

            class R:
                def execute(self):
                    # manual usa "after:dia before:dia"; scheduler 24h usa só "after:<epoch>"
                    if "before:" in consultas[-1]:
                        return {"messages": []}
                    return {"messages": [{"id": "1"}]}

            return R()

        def get(self, userId=None, id=None):
            class R:
                def execute(_):
                    return msgs[id]

            return R()

        def modify(self, **p):
            class R:
                def execute(self):
                    return {}

            return R()

    class FakeService:
        def __init__(self):
            class Users:
                def messages(self):
                    return FakeMessages()

            self._users = Users()

        def users(self):
            return self._users

    monkeypatch.setattr(resumidor_emails, "gerar_resumo_extrativo", lambda texto, n_frases=3: ("r", "portuguese"))
    console = Console(file=io.StringIO(), force_terminal=False, width=200)
    resultado = resumidor_emails.resumir_emails(
        service=FakeService(),
        prompter=lambda email: False,
        console=console,
        pager_input=lambda prompt="": "",
        perguntar_lista_negra=False,
    )
    assert {r["id"] for r in resultado["resumidos"]} == {"1"}
    assert consultas and all("before:" not in c for c in consultas)
    assert consultas[0].startswith("after:")
    # dia gravado = hoje (execução), não intervalo
    hoje = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    assert resultado["dia"] == hoje


def test_resumidor_manual_mantem_busca_por_dia(tmp_path, monkeypatch):
    import base64
    import io

    from rich.console import Console

    from gaia.routines import resumidor_emails

    monkeypatch.chdir(tmp_path)
    consultas = []

    b64 = lambda t: base64.urlsafe_b64encode(t.encode()).decode()
    msgs = {"1": {"payload": {"headers": [{"name": "From", "value": "Novo <novo@ex.com>"}, {"name": "Subject", "value": "S1"}, {"name": "Date", "value": "D"}], "mimeType": "text/plain", "body": {"data": b64("Texto longo para resumo de verdade um dois tres quatro.")}}, "threadId": "t1"}}

    class FakeMessages:
        def list(self, **p):
            consultas.append(p.get("q", ""))

            class R:
                def execute(self):
                    # manual usa "after:dia before:dia"; 24h usa só "after:<epoch>"
                    if "before:" in consultas[-1]:
                        return {"messages": [{"id": "1"}]}
                    return {"messages": []}

            return R()

        def get(self, userId=None, id=None):
            class R:
                def execute(_):
                    return msgs[id]

            return R()

        def modify(self, **p):
            class R:
                def execute(self):
                    return {}

            return R()

    class FakeService:
        def __init__(self):
            class Users:
                def messages(self):
                    return FakeMessages()

            self._users = Users()

        def users(self):
            return self._users

    monkeypatch.setattr(resumidor_emails, "gerar_resumo_extrativo", lambda texto, n_frases=3: ("r", "portuguese"))
    console = Console(file=io.StringIO(), force_terminal=False, width=200)
    resultado = resumidor_emails.resumir_emails(
        service=FakeService(),
        prompter=lambda email: False,
        console=console,
        pager_input=lambda prompt="": "",
    )
    assert {r["id"] for r in resultado["resumidos"]} == {"1"}
    assert consultas and all("before:" in c for c in consultas)
