def test_gaia_config_expoe_n_frases():
    from gaia.config import N_FRASES_RESUMO

    assert N_FRASES_RESUMO == 1

def test_gaia_config_expoe_monitor():
    from gaia import config

    assert config.MONITOR_INTERVALO_TELA == 1.0
    assert config.MONITOR_INTERVALO_FUNDO == 2.0
    assert config.MONITOR_THRESHOLD_AVISO == 80
    assert config.MONITOR_THRESHOLD_CRITICO == 90
    assert config.MONITOR_JANELA_SPARKLINE == 30
    assert config.HISTORICO_DIAS == 2

def test_monitor_coletar_metricas_com_fakes():
    from gaia.core.monitor import coletar_metricas

    resultado = coletar_metricas(
        get_cpu=lambda: 32.5,
        get_mem=lambda: {"percent": 45.0, "used_bytes": 4500, "total_bytes": 10000, "available_bytes": 5500},
        get_proc=lambda: {"cpu_percent": 2.1, "memory_mb": 48.0},
        agora="2026-11-09T10:00:00",
    )
    assert resultado["cpu_percent"] == 32.5
    assert resultado["ram_percent"] == 45.0
    assert resultado["ram_usada_bytes"] == 4500
    assert resultado["ram_total_bytes"] == 10000
    assert resultado["ram_disponivel_bytes"] == 5500
    assert resultado["gaia_cpu_percent"] == 2.1
    assert resultado["gaia_ram_mb"] == 48.0
    assert resultado["timestamp"] == "2026-11-09T10:00:00"

def test_monitor_buffer_acumula_e_retorna_ultimas():
    from gaia.core.monitor import Monitor

    mon = Monitor()
    assert mon.ultima_amostra() is None
    assert mon.ultimas_amostras(5) == []

    for i in range(5):
        mon.registrar({"cpu_percent": float(i * 10), "ram_percent": float(i * 5), "timestamp": f"t{i}"})

    assert mon.ultima_amostra()["cpu_percent"] == 40.0
    ultimas = mon.ultimas_amostras(2)
    assert [a["cpu_percent"] for a in ultimas] == [30.0, 40.0]
    assert mon.historico_cpu(5) == [0.0, 10.0, 20.0, 30.0, 40.0]
    assert mon.historico_ram(5) == [0.0, 5.0, 10.0, 15.0, 20.0]

def test_historico_filtra_hoje_e_ontem():
    from datetime import datetime

    from gaia.core.historico import filtrar_hoje_ontem

    amostras = [
        {"timestamp": "2026-11-07T10:00:00", "cpu_percent": 1.0},
        {"timestamp": "2026-11-08T10:00:00", "cpu_percent": 2.0},
        {"timestamp": "2026-11-09T10:00:00", "cpu_percent": 3.0},
        {"timestamp": "invalido", "cpu_percent": 9.0},
    ]
    filtradas = filtrar_hoje_ontem(amostras, hoje=datetime(2026, 11, 9, 12, 0).date())
    assert [a["cpu_percent"] for a in filtradas] == [2.0, 3.0]

def test_historico_resumo_pico_media():
    from gaia.core.historico import resumo_historico

    amostras = [
        {"cpu_percent": 10.0, "ram_percent": 20.0},
        {"cpu_percent": 30.0, "ram_percent": 40.0},
        {"cpu_percent": 50.0, "ram_percent": 60.0},
    ]
    resumo = resumo_historico(amostras)
    assert resumo["cpu_pico"] == 50.0
    assert resumo["cpu_media"] == 30.0
    assert resumo["ram_pico"] == 60.0
    assert resumo["ram_media"] == 40.0
    assert resumo["total"] == 3
    assert resumo_historico([])["total"] == 0

def test_historico_agrega_por_hora():
    from gaia.core.historico import agregar_por_hora

    amostras = [
        {"timestamp": "2026-11-09T14:05:00", "cpu_percent": 10.0, "ram_percent": 20.0},
        {"timestamp": "2026-11-09T14:55:00", "cpu_percent": 30.0, "ram_percent": 40.0},
        {"timestamp": "2026-11-09T15:10:00", "cpu_percent": 50.0, "ram_percent": 60.0},
    ]
    buckets = agregar_por_hora(amostras)
    assert len(buckets) == 2
    assert buckets[0]["hora"] == "2026-11-09 14:00"
    assert buckets[0]["cpu_pico"] == 30.0
    assert buckets[0]["cpu_media"] == 20.0
    assert buckets[1]["hora"] == "2026-11-09 15:00"

def test_historico_ranking_ordena_por_duracao_total():
    from gaia.core.historico import ranking_rotinas

    logs = [
        {"rotina": "resumir_emails", "duracao_s": 10.0, "cpu_s": 2.0, "ram_mb": 50.0},
        {"rotina": "outra", "duracao_s": 5.0, "cpu_s": 1.0, "ram_mb": 30.0},
        {"rotina": "resumir_emails", "duracao_s": 20.0, "cpu_s": 4.0, "ram_mb": 60.0},
    ]
    ranking = ranking_rotinas(logs)
    assert ranking[0]["rotina"] == "resumir_emails"
    assert ranking[0]["execucoes"] == 2
    assert ranking[0]["duracao_total_s"] == 30.0
    assert ranking[0]["cpu_total_s"] == 6.0

def test_storage_anexa_amostra_jsonl_e_carrega_ultimas(tmp_path, monkeypatch):
    import json

    from gaia.core.storage import anexar_monitor_amostra, carregar_amostras_monitor

    monkeypatch.chdir(tmp_path)
    anexar_monitor_amostra({"timestamp": "t1", "cpu_percent": 10.0, "ram_percent": 20.0})
    anexar_monitor_amostra({"timestamp": "t2", "cpu_percent": 30.0, "ram_percent": 40.0})
    anexar_monitor_amostra({"timestamp": "t3", "cpu_percent": 50.0, "ram_percent": 60.0})

    linhas = (tmp_path / "monitor_historico.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(linhas) == 3
    assert json.loads(linhas[0])["cpu_percent"] == 10.0

    ultimas = carregar_amostras_monitor(2)
    assert [a["cpu_percent"] for a in ultimas] == [30.0, 50.0]
    assert carregar_amostras_monitor(5) and len(carregar_amostras_monitor(5)) == 3

def test_storage_anexa_log_rotina_jsonl(tmp_path, monkeypatch):
    import json

    from gaia.core.storage import anexar_log_rotina, carregar_logs_rotina

    monkeypatch.chdir(tmp_path)
    anexar_log_rotina({"rotina": "resumir_emails", "duracao_s": 1.5})
    anexar_log_rotina({"rotina": "resumir_emails", "duracao_s": 2.5})

    linhas = (tmp_path / "monitor_rotinas.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(linhas[1])["duracao_s"] == 2.5
    logs = carregar_logs_rotina(1)
    assert len(logs) == 1 and logs[0]["duracao_s"] == 2.5

def test_monitor_registrar_execucao_rotina_grava_log(tmp_path, monkeypatch):
    from gaia.core.monitor import registrar_execucao_rotina
    from gaia.core.storage import carregar_logs_rotina

    monkeypatch.chdir(tmp_path)
    registrar_execucao_rotina("resumir_emails", duracao_s=1.5, cpu_s=0.8, ram_mb=52.0)

    logs = carregar_logs_rotina(1)
    assert logs[0]["rotina"] == "resumir_emails"
    assert logs[0]["duracao_s"] == 1.5
    assert logs[0]["cpu_s"] == 0.8
    assert logs[0]["ram_mb"] == 52.0
    assert "timestamp" in logs[0]

def test_monitor_medir_rotina_mede_e_registra(tmp_path, monkeypatch):
    from gaia.core import monitor
    from gaia.core.storage import carregar_logs_rotina

    monkeypatch.chdir(tmp_path)

    @monitor.medir_rotina("resumir_emails")
    def rotina_falsa():
        return "ok"

    assert rotina_falsa() == "ok"
    logs = carregar_logs_rotina(1)
    assert logs[0]["rotina"] == "resumir_emails"
    assert logs[0]["duracao_s"] >= 0

def test_main_criar_monitor_esta_ligado_com_sampler():
    import main as gaia_main

    mon = gaia_main.criar_monitor()
    assert mon.intervalo == 2.0
    assert mon.salvar_fn is not None
    assert mon.ultima_amostra() is None
    mon.registrar({"cpu_percent": 10.0, "ram_percent": 20.0, "timestamp": "t"})
    assert mon.ultima_amostra()["cpu_percent"] == 10.0

def test_main_resumir_emails_e_scheduler_mendem_rotina(tmp_path, monkeypatch):
    import main as gaia_main
    from gaia.core.storage import carregar_logs_rotina

    monkeypatch.chdir(tmp_path)
    chamadas = []

    def fake_impl(**kwargs):
        chamadas.append(kwargs)
        return {"dia": None, "resumidos": [], "ignorados": []}

    monkeypatch.setattr(gaia_main, "_resumir_emails_impl", fake_impl)

    assert gaia_main.resumir_emails() == {"dia": None, "resumidos": [], "ignorados": []}
    tarefa = gaia_main.criar_tarefa_scheduler()
    tarefa()

    logs = carregar_logs_rotina(5)
    assert len(logs) == 2
    assert all(l["rotina"] == "resumir_emails" for l in logs)

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
        resumo_fn=lambda texto, n_frases=3: ("r", "portuguese"),
    )
    assert resultado["ignorado"] is True
    assert "resumo" not in resultado

def test_processar_mensagem_nao_depende_de_ui_no_resumo():
    import base64

    from gaia.routines.resumidor_emails import processar_mensagem


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
    assert chamadas == {}

def test_scheduler_exibe_traceback_em_erro(capsys):
    from gaia.scheduler import executar_com_traceback

    def tarefa_falha():
        raise RuntimeError("boom-scheduler")

    executar_com_traceback(tarefa_falha)
    capturado = capsys.readouterr()
    saida = capturado.out + capturado.err
    assert "boom-scheduler" in saida
    assert "Traceback" in saida


def test_resumidor_24h_nao_interage_e_marca_pendente(tmp_path, monkeypatch):
    import base64
    from datetime import datetime, timezone

    from gaia.routines import resumidor_emails

    monkeypatch.chdir(tmp_path)
    resumidor_emails.limpar_resumo_pendente()
    consultas = []

    b64 = lambda t: base64.urlsafe_b64encode(t.encode()).decode()
    msgs = {
        "1": {
            "payload": {
                "headers": [{"name": "From", "value": "Novo <novo@ex.com>"}, {"name": "Subject", "value": "S1"}, {"name": "Date", "value": "D"}],
                "mimeType": "text/plain",
                "body": {"data": b64("Texto longo para resumo de verdade um dois tres quatro cinco.")},
            },
            "threadId": "t1",
        }
    }

    class FakeMessages:
        def list(self, **params):
            consultas.append(params.get("q", ""))

            class Response:
                def execute(self):
                    return {"messages": [{"id": "1"}]}

            return Response()

        def get(self, userId=None, id=None):
            class Response:
                def execute(self):
                    return msgs[id]

            return Response()

        def modify(self, **params):
            class Response:
                def execute(self):
                    return {}

            return Response()

    class FakeService:
        def users(self):
            class Users:
                def messages(self):
                    return FakeMessages()

            return Users()

    monkeypatch.setattr(resumidor_emails, "gerar_resumo_extrativo", lambda texto, n_frases=3: ("resumo", "portuguese"))
    progresso = []
    resultado = resumidor_emails.resumir_emails(
        service=FakeService(),
        on_progress=progresso.append,
        agora=datetime(2026, 11, 9, 12, tzinfo=timezone.utc),
    )

    assert {item["id"] for item in resultado["resumidos"]} == {"1"}
    assert consultas and all(query.startswith("after:") and "before:" not in query for query in consultas)
    assert progresso and any("Email 1/1" in mensagem for mensagem in progresso)
    assert resumidor_emails.tem_resumo_pendente() is True
    assert list(tmp_path.glob("resumo_dia_*.json"))
    resumidor_emails.limpar_resumo_pendente()


def test_resumidor_recusa_execucao_concorrente(tmp_path, monkeypatch):
    from gaia.routines import resumidor_emails

    monkeypatch.chdir(tmp_path)
    resumidor_emails._execucao_lock.acquire()
    try:
        resultado = resumidor_emails.resumir_emails(service=object())
    finally:
        resumidor_emails._execucao_lock.release()

    assert resultado == {"dia": None, "resumidos": [], "ignorados": [], "falhas": []}


def test_tts_montar_texto_leitura():
    from gaia.core import tts

    texto = tts.montar_texto({"de": "Ana <ana@x.com>", "assunto": "Oi", "resumo": "Resumo curto."})
    assert "Ana" in texto
    assert "Oi" in texto
    assert "Resumo curto." in texto


def test_tts_falar_usa_kokoro_e_para(monkeypatch, tmp_path):
    import numpy as np

    from gaia.core import tts

    chamadas = []

    class KokoroFake:
        def create(self, texto, voice, lang, speed):
            chamadas.append(("create", texto, voice, lang, speed))
            return np.zeros(2400, dtype=np.float32), 24000

    class ProcFake:
        def __init__(self):
            self.terminado = False

        def terminate(self):
            self.terminado = True
            chamadas.append(("terminate",))

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return None if not self.terminado else 0

    monkeypatch.setattr(tts, "_carregar_kokoro", lambda: KokoroFake())
    monkeypatch.setattr(tts.soundfile, "write", lambda *a, **k: chamadas.append(("write",)))
    monkeypatch.setattr(tts.subprocess, "Popen", lambda cmd, **k: chamadas.append(("popen", cmd)) or ProcFake())
    tts.falar("olá")
    import time
    for _ in range(200):
        if any(c[0] == "popen" for c in chamadas):
            break
        time.sleep(0.01)
    tts.parar()
    assert any(c[0] == "create" and c[1] == "olá" and c[2] == "pf_dora" for c in chamadas)
    assert ("terminate",) in chamadas


def test_bridge_sair_para_leitura(monkeypatch):
    from gaia.core import tts
    from gaia.ui import webview_app

    parou = []
    monkeypatch.setattr(tts, "parar", lambda: parou.append(True) or {"falando": False})

    class JanelaFake:
        def destroy(self):
            pass

    bridge = webview_app.GaiaBridge()
    bridge.window = JanelaFake()
    resultado = bridge.sair()
    assert resultado["fechando"] is True
    assert parou == [True]
