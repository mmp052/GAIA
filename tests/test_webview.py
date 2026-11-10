"""Testes da migração completa para PyWebview."""


class FakeMonitor:
    def __init__(self):
        self.iniciado = False
        self.amostra = {
            "cpu_percent": 100.0,
            "ram_percent": 52.5,
            "gaia_cpu_percent": 3.25,
            "gaia_ram_mb": 48.0,
            "ram_usada_bytes": 6 * 1024**3,
            "ram_total_bytes": 16 * 1024**3,
            "timestamp": "2026-11-09T16:23:45",
        }
        self.cpu = [10.0, 50.0, 100.0]
        self.ram = [20.0, 40.0, 52.5]

    def ultima_amostra(self):
        return self.amostra

    def historico_cpu(self, janela):
        assert janela == 30
        return self.cpu[-janela:]

    def historico_ram(self, janela):
        assert janela == 30
        return self.ram[-janela:]


def test_webview_bridge_monitor_estado():
    from gaia.ui.webview_app import GaiaBridge

    bridge = GaiaBridge(monitor=FakeMonitor(), rotinas=[("1", "Resumidor de Emails", lambda: {})])
    estado = bridge.monitor_estado()

    assert estado["cpu"]["valor"] == 100.0
    assert estado["cpu"]["historico"] == [10.0, 50.0, 100.0]
    assert estado["ram"]["valor"] == 52.5
    assert estado["gaia"]["cpu"] == 3.25
    assert estado["gaia"]["ram_mb"] == 48.0
    assert estado["status"].startswith("aviso")

def test_webview_app_cria_janela_com_bridge(monkeypatch):
    import sys
    from types import SimpleNamespace

    class FakeWindow:
        pass

    calls = {}
    fake_window = FakeWindow()

    def create_window(title, **kwargs):
        calls["title"] = title
        calls["kwargs"] = kwargs
        return fake_window

    def start(**kwargs):
        calls["start"] = kwargs

    fake_webview = SimpleNamespace(create_window=create_window, start=start, windows=[fake_window])
    monkeypatch.setitem(sys.modules, "webview", fake_webview)

    from gaia.ui import webview_app

    app = webview_app.criar_app_pywebview(monitor=FakeMonitor(), rotinas=[("1", "Resumidor de Emails", lambda: {})])
    app.run()

    assert calls["title"] == "GAIA"
    assert calls["kwargs"]["js_api"] is app.bridge
    assert calls["kwargs"]["url"].endswith("gaia/ui/web/index.html")
    assert "start" in calls

def test_webview_front_puro_tem_telas_e_atalhos():
    from pathlib import Path

    web = Path(__file__).parents[1] / "gaia" / "ui" / "web"
    html = (web / "index.html").read_text(encoding="utf-8")
    js = (web / "app.js").read_text(encoding="utf-8")
    css = (web / "style.css").read_text(encoding="utf-8")

    for screen in ("home", "resumidor", "leitura", "email", "historico"):
        assert f'data-screen="{screen}"' in html
    for control in ("buscar-novos", "modal-confirmacao", "email-gmail", "monitor-cpu", "monitor-ram"):
        assert control in html
    # Seleção navega; nada executa sem o modal de confirmação "Sim, executar".
    assert "monitor_estado" in js
    assert "iniciar_busca" in js
    assert "sim, executar" in html.lower()
    # Gráfico de linha fluido em canvas (bezier); pontos só para hover no histórico.
    assert "<canvas" in html
    assert "bezierCurveTo" in js
    assert "stroke" in js
    assert "--bg" in css and "#A78BFA" in css

def test_webview_busca_roda_em_background_e_expoe_status():
    import threading
    import time

    from gaia.ui.webview_app import GaiaBridge

    started = threading.Event()
    release = threading.Event()

    def fake_busca(on_progress=None):
        on_progress("Email 1/1 — resumindo")
        started.set()
        assert release.wait(2)
        return {"dia": "2026-11-09", "resumidos": [{"id": "1"}], "ignorados": []}

    bridge = GaiaBridge(monitor=FakeMonitor(), rotinas=[], buscar_novos=fake_busca)
    resposta = bridge.iniciar_busca()

    assert resposta == {"iniciada": True}
    assert started.wait(1)
    em_andamento = bridge.busca_estado()
    assert em_andamento["executando"] is True
    assert "Email 1/1" in em_andamento["progresso"]
    assert bridge.iniciar_busca() == {"iniciada": False}

    release.set()
    for _ in range(100):
        time.sleep(0.01)
        if not bridge.busca_estado()["executando"]:
            break
    final = bridge.busca_estado()
    assert final["executando"] is False
    assert final["resultado"]["resumidos"][0]["id"] == "1"

def test_webview_historico_roda_em_background_e_expoe_dados():
    import threading
    import time

    from gaia.ui.webview_app import GaiaBridge

    started = threading.Event()
    release = threading.Event()

    def fake_historico():
        started.set()
        assert release.wait(2)
        return {"resumo": {"total": 42}, "ranking": [{"rotina": "resumir_emails"}], "por_hora": [{"cpu_pico": 10}]}

    bridge = GaiaBridge(monitor=FakeMonitor(), rotinas=[], historico_fn=fake_historico)
    assert bridge.iniciar_historico() == {"iniciada": True}
    assert started.wait(1)
    assert bridge.historico_estado()["executando"] is True
    assert bridge.iniciar_historico() == {"iniciada": False}
    release.set()
    for _ in range(100):
        time.sleep(0.01)
        if not bridge.historico_estado()["executando"]:
            break
    final = bridge.historico_estado()
    assert final["dados"]["resumo"]["total"] == 42
    assert final["erro"] is None

def test_webview_bridge_expõe_pendencia_de_resumo(monkeypatch):
    import gaia.ui.webview_app as webview_app

    monkeypatch.setattr(webview_app, "tem_resumo_pendente", lambda: True)
    bridge = webview_app.GaiaBridge(monitor=FakeMonitor(), rotinas=[])

    assert bridge.resumo_pendente() is True

def test_webview_bridge_ler_ultimo_resumo(monkeypatch):
    import gaia.ui.webview_app as webview_app

    salvo = {"dia": "2026-11-09", "resumidos": [{"id": "1", "resumo": "ok"}]}
    monkeypatch.setattr(webview_app, "carregar_ultimo_resumo", lambda: salvo)
    bridge = webview_app.GaiaBridge(monitor=FakeMonitor(), rotinas=[])

    assert bridge.ler_ultimo_resumo() == salvo

def test_webview_bridge_abre_somente_links_do_gmail(monkeypatch):
    import gaia.ui.webview_app as webview_app

    abertos = []
    monkeypatch.setattr(webview_app.webbrowser, "open", lambda url: abertos.append(url) or True)
    bridge = webview_app.GaiaBridge(monitor=FakeMonitor(), rotinas=[])

    permitido = bridge.abrir_gmail("https://mail.google.com/mail/#all/abc123")
    negado = bridge.abrir_gmail("https://example.com/phishing")

    assert permitido == {"aberto": True, "mensagem": ""}
    assert abertos == ["https://mail.google.com/mail/#all/abc123"]
    assert negado["aberto"] is False
    assert "Gmail" in negado["mensagem"]

def test_webview_bridge_sair_fecha_janela():
    from gaia.ui.webview_app import GaiaBridge

    class FakeWindow:
        def __init__(self):
            self.destroyed = False

        def destroy(self):
            self.destroyed = True

    bridge = GaiaBridge(monitor=FakeMonitor(), rotinas=[])
    window = FakeWindow()
    bridge.window = window

    assert bridge.sair() == {"fechando": True}
    assert window.destroyed is True

def test_main_entrypoint_usa_pywebview(monkeypatch):
    import main

    chamadas = []
    monkeypatch.setattr(main, "executar_pywebview", lambda: chamadas.append(True))

    main.main()

    assert chamadas == [True]

def test_requirements_migrou_para_pywebview():
    from pathlib import Path

    deps = Path(__file__).resolve().parents[1].joinpath("requirements.txt").read_text(encoding="utf-8").lower()

    assert "pywebview" in deps
    assert "rich" not in deps
    assert "textual" not in deps
    assert "pyfiglet" not in deps

def test_config_expoe_entrada_pywebview():
    import gaia.config as config

    assert config.WEBVIEW_TITULO == "GAIA"
    assert config.WEBVIEW_LARGURA >= 720
    assert config.WEBVIEW_ALTURA >= 480
    assert isinstance(config.WEBVIEW_INTERVALO_TELA, float)
    assert not hasattr(config, "TEXTUAL_INTERVALO_TELA")

def test_webview_bridge_ler_ultimo_resumo_limpa_pendencia(monkeypatch):
    import gaia.ui.webview_app as webview_app

    salvo = {"dia": "2026-11-09", "resumidos": [{"id": "1"}]}
    limpezas = []
    monkeypatch.setattr(webview_app, "carregar_ultimo_resumo", lambda: salvo)
    monkeypatch.setattr(webview_app, "limpar_resumo_pendente", lambda: limpezas.append(True))
    bridge = webview_app.GaiaBridge(monitor=FakeMonitor(), rotinas=[])

    assert bridge.ler_ultimo_resumo() == salvo
    assert limpezas == [True]

def test_webview_run_força_qt_no_linux(monkeypatch):
    import gaia.ui.webview_app as webview_app

    chamadas = []
    fake_webview = type("FakeWebview", (), {"start": staticmethod(lambda **kwargs: chamadas.append(kwargs))})()
    bridge = webview_app.GaiaBridge(monitor=FakeMonitor(), rotinas=[])
    app = webview_app.GaiaWebviewApp(bridge=bridge, window=object(), webview_module=fake_webview)
    monkeypatch.setattr(webview_app.platform, "system", lambda: "Linux")

    app.run()

    assert chamadas[0]["gui"] == "qt"
    assert callable(chamadas[0]["func"])

def test_webview_bridge_identifica_historico_nas_rotinas():
    from gaia.ui.webview_app import GaiaBridge

    def fake_historico():
        return {"resumo": {"total": 7}}

    bridge = GaiaBridge(monitor=FakeMonitor(), rotinas=[("2", "Histórico", fake_historico)])

    assert bridge.historico_fn is fake_historico

def test_webview_front_removeu_tema_claro():
    from pathlib import Path

    web = Path(__file__).resolve().parents[1] / "gaia" / "ui" / "web"
    html = (web / "index.html").read_text(encoding="utf-8")
    css = (web / "style.css").read_text(encoding="utf-8")
    js = (web / "app.js").read_text(encoding="utf-8")

    assert 'id="theme-toggle"' not in html
    assert 'd tema' not in html
    assert '[data-theme="light"]' not in css
    assert "toggleTheme" not in js
    assert "'d'" not in js and '"d"' not in js
    assert 'd tema' not in js

def test_webview_front_historico_tem_eixos_grade_e_tooltip():
    from pathlib import Path

    web = Path(__file__).resolve().parents[1] / "gaia" / "ui" / "web"
    html = (web / "index.html").read_text(encoding="utf-8")
    js = (web / "app.js").read_text(encoding="utf-8")
    css = (web / "style.css").read_text(encoding="utf-8")

    # Hover disponível em cada gráfico, com tooltip próprio e posicionamento por canvas.
    for chart in ("chart-tooltip-cpu", "chart-tooltip-ram"):
        assert chart in html
    assert "mousemove" in js
    assert "mouseleave" in js
    assert "getBoundingClientRect" in js
    assert "textContent" in js

    # Eixos X/Y, grade pontilhada e textos de ticks.
    assert "drawHistoricoChart" in js
    assert "setLineDash" in js
    assert "ctx.fillText" in js
    assert "ctx.moveTo" in js and "ctx.lineTo" in js
    assert "axes" not in css  # eixos são desenhados no canvas, sem framework
    assert ".chart-tooltip" in css

def test_webview_run_processa_eventos_qt_antes_do_exit(monkeypatch):
    import sys
    from types import SimpleNamespace

    import gaia.ui.webview_app as webview_app

    chamadas = []

    class FakeApp:
        def processEvents(self):
            chamadas.append("processEvents")

        def exit(self):
            chamadas.append("exit")

    fake_app = FakeApp()
    fake_qt = SimpleNamespace(_app=fake_app)

    def start(**kwargs):
        chamadas.append("start")
        func = kwargs.get("func")
        if callable(func):
            func()

    fake_webview = SimpleNamespace(start=start)
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    monkeypatch.setitem(sys.modules, "webview.platforms.qt", fake_qt)
    monkeypatch.setattr(webview_app.platform, "system", lambda: "Linux")

    bridge = webview_app.GaiaBridge(monitor=FakeMonitor(), rotinas=[])
    app = webview_app.GaiaWebviewApp(bridge=bridge, window=object(), webview_module=fake_webview)
    app.run()
    fake_app.exit()

    assert chamadas == ["start", "processEvents", "exit"]

def test_webview_patch_exit_qt_envia_eventos_deferred_delete(monkeypatch):
    import sys
    from types import SimpleNamespace

    import gaia.ui.webview_app as webview_app

    chamadas = []
    deferred_delete = "DeferredDelete"

    class FakeQCoreApplication:
        @staticmethod
        def sendPostedEvents(obj, event_type):
            chamadas.append(("sendPostedEvents", obj, event_type))

    fake_qtcore = SimpleNamespace(
        QCoreApplication=FakeQCoreApplication,
        QEvent=SimpleNamespace(Type=SimpleNamespace(DeferredDelete=deferred_delete)),
    )

    class FakeApp:
        def processEvents(self):
            chamadas.append("processEvents")

        def exit(self):
            chamadas.append("exit")

    fake_app = FakeApp()
    fake_qt = SimpleNamespace(_app=fake_app, QtCore=fake_qtcore)
    monkeypatch.setitem(sys.modules, "webview.platforms.qt", fake_qt)

    webview_app._instalar_patch_exit_qt()
    fake_app.exit()

    assert chamadas == ["processEvents", ("sendPostedEvents", None, deferred_delete), "exit"]

def test_executar_pywebview_coleta_objetos_qt_antes_de_sair(monkeypatch):
    import main

    chamadas = []

    class FakeMonitor:
        def iniciar(self):
            chamadas.append("monitor iniciar")

        def parar(self):
            chamadas.append("monitor parar")

    class FakeScheduler:
        def __init__(self, *args, **kwargs):
            chamadas.append("scheduler criar")

        def start(self):
            chamadas.append("scheduler start")

        def stop(self):
            chamadas.append("scheduler stop")

    class FakeApp:
        def run(self):
            chamadas.append("app run")

    collection = []
    monkeypatch.setattr(main, "criar_monitor", lambda: FakeMonitor())
    monkeypatch.setattr(main, "Scheduler", FakeScheduler)
    monkeypatch.setattr(main, "criar_app_pywebview", lambda monitor: FakeApp())
    monkeypatch.setattr(main.gc, "collect", lambda *args, **kwargs: collection.append(True))

    main.executar_pywebview()

    assert chamadas == ["scheduler criar", "scheduler start", "monitor iniciar", "app run", "monitor parar", "scheduler stop"]
    assert collection == [True]

def test_webview_home_redesenhada_com_holograma_gaia():
    from pathlib import Path

    web = Path(__file__).resolve().parents[1] / "gaia" / "ui" / "web"
    html = (web / "index.html").read_text(encoding="utf-8")
    css = (web / "style.css").read_text(encoding="utf-8")
    js = (web / "app.js").read_text(encoding="utf-8")

    # Holograma procedural substitui o logo ASCII.
    assert 'id="gaia-orb"' in html
    assert 'class="logo"' not in html
    assert "dP\"\"b8" not in html  # nenhuma arte ASCII antiga

    # Palco da home em HUD: painéis laterais + núcleo central (sem wordmark redundante).
    for marker in ("orb-stage", "hud-panel", "hud-label"):
        assert marker in html
    assert 'class="wordmark"' not in html
    assert "Gestão e Assistência" not in html

    # Renderizador 3D procedural no front (esfera wireframe, anéis, partículas, rAF).
    assert "gaia-orb" in js
    assert "requestAnimationFrame" in js
    assert "bezierCurveTo" in js or "projectPoint" in js
    assert "prefers-reduced-motion" in js
    # Holograma segue o envelope sonoro embutido (análise offline do MP3),
    # sempre ligado, sem botão de play.
    assert "GAIA_ENVELOPE" in js
    assert "envelopeSample" in js
    assert "toggleOrbTheme" not in js
    assert 'id="orb-toggle"' not in html
    # Esfera renderizada com Arcade (OpenGL) e animada em loop no canvas.
    assert "ORB_FRAME_COUNT" in js

    # Painéis HUD com cantos sci-fi e grade de fundo na home.
    assert ".hud-panel" in css
    assert ".gaia-orb" in css
    assert ".orb-stage" in css
    assert "home-grid" in css

    # Canvas em tela cheia: a luz ambiente chega ao fundo inteiro (sem "quadrado").
    regra_orb = css.split(".gaia-orb", 1)[1].split("}", 1)[0]
    assert "inset: 0" in regra_orb
    assert "width: 100%" in regra_orb
    assert "height: 100%" in regra_orb
    assert "pointer-events: auto" in regra_orb  # os planetas recebem cliques
    assert "orbViewRect" in js
    assert "canvas.height" in js

    # Monitor continua na home; o painel AÇÕES deu lugar aos planetas orbitais.
    for control in ("monitor-cpu", "monitor-ram"):
        assert control in html
    assert "hud-actions" not in html
    assert "hud-actions" not in css
    assert "menu-resumidor" not in html
    assert "menu-historico" not in html
    assert "menu-sair" not in html

def test_webview_envelope_loser_versionado():
    import json
    import re
    from pathlib import Path

    asset = Path(__file__).parents[1] / "gaia" / "ui" / "web" / "assets" / "loser_envelope.js"
    assert asset.is_file()
    content = asset.read_text(encoding="utf-8")
    assert "window.GAIA_ENVELOPE" in content
    payload = json.loads(re.sub(r"^\s*window\.GAIA_ENVELOPE\s*=\s*|;?\s*$", "", content.strip(), count=1).strip().rstrip(";"))
    assert payload["duracao_s"] > 200
    assert payload["janela_ms"] == 100
    frames = payload["frames"]
    assert len(frames) == round(payload["duracao_s"] * 10)
    for frame in frames:
        assert len(frame) == 4  # rms, graves, médios, agudos
        assert all(0.0 <= value <= 1.0 for value in frame)


def test_webview_ferramenta_gera_envelope():
    from pathlib import Path

    tool = Path(__file__).parents[1] / "tools" / "gerar_envelope_gaia.py"
    assert tool.is_file()
    content = tool.read_text(encoding="utf-8")
    assert "__main__" in content
    assert "GAIA_ENVELOPE" in content
    assert "soundfile" in content

def test_webview_frames_esfera_arcade():
    from pathlib import Path

    orb_dir = Path(__file__).parents[1] / "gaia" / "ui" / "web" / "assets" / "orb"
    frames = sorted(orb_dir.glob("frame_*.webp"))
    assert len(frames) >= 48
    assert all(frame.stat().st_size > 4000 for frame in frames)  # frame vazio ficaria ~1 KB


def test_tool_gerar_esfera_arcade():
    from pathlib import Path

    tool = Path(__file__).parents[1] / "tools" / "gerar_esfera_gaia.py"
    assert tool.is_file()
    content = tool.read_text(encoding="utf-8")
    assert "arcade" in content
    assert "__main__" in content
    # Matemática do holograma (glows da referência), sem anéis/raios/giroscópios.
    assert "Shadertoy" in content
    assert "mainImage" in content
    assert "JarvisMatrix" not in content
    assert "atan(uv.y, uv.x) * 12.0" not in content
    assert "draw_arc_outline" not in content  # fragmentos giroscópio removidos
    assert "Flare horizontal" not in content  # a "anel de Saturno" no centro saiu

def test_webview_home_sem_anel_externo_tipo_relogio():
    from pathlib import Path

    web = Path(__file__).resolve().parents[1] / "gaia" / "ui" / "web"
    js = (web / "app.js").read_text(encoding="utf-8")

    # O anel externo HUD (trilha + arco tracejado + 72 ticks) foi removido.
    assert "for (let tick = 0; tick < 72; tick += 1)" not in js
    assert "sphereRadius * 1.86" not in js
    # Fica só a esfera central — satélites orbitais e suas partículas saíram.
    assert "drawSize" in js
    assert "drawOrbitRing" not in js
    assert "orbProjector" not in js
    assert "projectPoint" not in js

def test_webview_sem_luzes_de_fundo_nos_cantos():
    from pathlib import Path

    web = Path(__file__).resolve().parents[1] / "gaia" / "ui" / "web"
    css = (web / "style.css").read_text(encoding="utf-8")

    # Sem focos de luz ambiente nos cantos: a luz vem só da esfera.
    assert "circle at 15% 10%" not in css
    assert "circle at 85% 75%" not in css
    assert "radial-gradient" not in css.split("body {")[1].split("}")[0]

def test_webview_home_sem_elipse_fixa_e_luz_ambiente_da_esfera():
    from pathlib import Path

    web = Path(__file__).resolve().parents[1] / "gaia" / "ui" / "web"
    css = (web / "style.css").read_text(encoding="utf-8")
    js = (web / "app.js").read_text(encoding="utf-8")

    # Sem a elipse de luz fixa do CSS atrás da esfera.
    assert "ellipse at 50% 42%" not in css

    # Luz ambiente do menu desenhada no canvas, ancorada na esfera e modulada pelo envelope.
    assert "drawAmbientLight" in js
    assert "createRadialGradient" in js
    assert "energy" in js  # escala/força do halo acompanham o RMS do envelope
    assert "orbAudioLevels" in js


def test_webview_planetas_orbitam_a_esfera_como_planetas():
    from pathlib import Path

    web = Path(__file__).resolve().parents[1] / "gaia" / "ui" / "web"
    html = (web / "index.html").read_text(encoding="utf-8")
    css = (web / "style.css").read_text(encoding="utf-8")
    js = (web / "app.js").read_text(encoding="utf-8")

    # Painel AÇÕES removido; a home tem só o monitor e a esfera com seus planetas.
    assert "hud-actions" not in html
    assert "AÇÕES" not in html
    assert "orb-stage" in html
    assert 'id="gaia-orb"' in html
    # Zero fica no footer; nada de menu de ações na home.
    assert "<footer" in html and "q" in html

    # Planetas desenhados no canvas da esfera (atrás dela quando no fundo da órbita),
    # com parâmetros procedurais distintos (seed fixa por planeta → estável entre boots).
    assert "ORBIT_PLANETS" in js
    assert "mulberry32" in js
    assert "orbitParams" in js
    # Cada planeta mostra seu ícone: envelope (Resumidor) e gráfico (Histórico).
    assert "'envelope'" in js
    assert "'chart'" in js
    # Ordem de pintura: planetas atrás da esfera antes dela; na frente depois.
    assert "drawOrbitingPlanets(ctx, false" in js
    assert "drawOrbitingPlanets(ctx, true" in js
    # Clique no planeta abre a tela correspondente (hit test geométrico).
    assert "planetAtPoint" in js
    # Profundidade: fundo menor/esmaecido, frente maior/opaco.
    assert "orbitDepth" in js

    # Número da tecla em cada planeta e legenda sempre visível.
    assert "planet.badge" in js or "badge" in js

    # O grid deixa cliques passarem para o canvas (que fica atrás), mantendo os painéis ativos.
    assert "pointer-events: none" in css.split(".home-grid", 1)[1].split("}", 1)[0]
    assert "pointer-events: auto" in css.split(".hud-panel", 1)[1].split("}", 1)[0]

    # Teclas 1 e 2 continuam abrindo as rotinas na home.
    assert "showScreen('resumidor')" in js
    assert "showScreen('historico')" in js

def test_webview_home_sem_texto_hint_da_esfera():
    from pathlib import Path

    web = Path(__file__).resolve().parents[1] / "gaia" / "ui" / "web"
    html = (web / "index.html").read_text(encoding="utf-8")
    js = (web / "app.js").read_text(encoding="utf-8")
    css = (web / "style.css").read_text(encoding="utf-8")

    # Sem o texto "scheduler 06:00 · 1/2 abrir" sob a esfera: a home fica só com a esfera e os planetas.
    assert "home-hint" not in html
    assert "home-hint" not in js
    assert "scheduler 06:00" not in html
    assert "1/2 abrir" not in html
    assert ".hint" not in css
