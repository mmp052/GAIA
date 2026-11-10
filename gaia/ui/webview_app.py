"""PyWebview do GAIA — janela desktop com HTML/CSS/JavaScript puro.

A ponte (`GaiaBridge`) expõe métodos pequenos e serializáveis para o front:
o JavaScript nunca executa código Python direto e nenhuma rotina roda por
simples navegação/seleção.
"""

import platform
import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

from gaia.config import MONITOR_JANELA_SPARKLINE, MONITOR_THRESHOLD_AVISO, MONITOR_THRESHOLD_CRITICO, WEBVIEW_ALTURA, WEBVIEW_INTERVALO_TELA, WEBVIEW_LARGURA, WEBVIEW_TITULO
from gaia.routines.resumidor_emails import limpar_resumo_pendente, tem_resumo_pendente
from gaia.core.storage import carregar_ultimo_resumo

ASSETS = Path(__file__).with_name("web")


def _aguardar_e_instalar_patch_exit_qt(timeout_s=2.0):
    """Aguarda o QApplication do PyWebview e instala o patch de encerramento."""
    import time

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        _instalar_patch_exit_qt()
        try:
            import importlib

            qt = importlib.import_module("webview.platforms.qt")

            app = getattr(qt, "_app", None)
            if app is not None and getattr(app, "_gaia_exit_patch", False):
                return True
        except Exception:
            pass
        time.sleep(0.01)
    return False


def _instalar_patch_exit_qt():
    """Drena deferred deletes do QtWebEngine antes de encerrar a aplicação.

    O PyWebview Qt chama `QApplication.exit()` imediatamente no `closeEvent`,
    antes de o `deleteLater()` do WebEnginePage ser processado. Isso pode deixar
    o processo e o perfil Qt numa ordem ruim. O patch não inicia uma nova
    interface: apenas processa eventos pendentes antes da chamada original de
    `exit`. Se a API interna mudar, o encerramento normal continua funcionando.
    """
    try:
        import importlib

        qt = importlib.import_module("webview.platforms.qt")

        app = getattr(qt, "_app", None)
        if app is None or getattr(app, "_gaia_exit_patch", False):
            return
        exit_original = app.exit

        def exit_com_delecoes_pendentes(*args, **kwargs):
            try:
                app.processEvents()
                try:
                    qevent_type = qt.QtCore.QEvent.Type.DeferredDelete
                    qt.QtCore.QCoreApplication.sendPostedEvents(None, qevent_type)
                except Exception:
                    # Não bloqueia a saída caso a API Qt interna mude.
                    pass
            finally:
                exit_original(*args, **kwargs)

        app.exit = exit_com_delecoes_pendentes
        app._gaia_exit_patch = True
    except Exception:
        # Best effort: PyWebview/Qt continua aceitando o fechamento sem o workaround.
        pass


def _fmt_bytes(bytes_total):
    gib = bytes_total / 1024 / 1024 / 1024
    if gib >= 1:
        return f"{gib:.1f}GB"
    return f"{bytes_total / 1024 / 1024:.0f}MB"


def _threshold(valor):
    valor = float(valor)
    if valor >= MONITOR_THRESHOLD_CRITICO:
        return "red"
    if valor >= MONITOR_THRESHOLD_AVISO:
        return "yellow"
    return "green"


class GaiaBridge:
    """API exposta ao JavaScript via ``window.pywebview.api``."""

    def __init__(self, monitor=None, rotinas=None, buscar_novos=None, historico_fn=None):
        self.monitor = monitor
        self.rotinas = list(rotinas or [])
        self.buscar_novos = buscar_novos or self._rotina("1")
        self.historico_fn = historico_fn or self._rotina("2")
        self.window = None
        self._historico_lock = threading.Lock()
        self._historico_state = {
            "executando": False,
            "status": "Pronto.",
            "dados": None,
            "erro": None,
        }
        self._busca_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._busca_state = {
            "executando": False,
            "status": "Pronto.",
            "progresso": "",
            "resultado": None,
            "erro": None,
        }

    def _rotina(self, tecla):
        for identificador, _titulo, funcao in self.rotinas:
            if str(identificador) == str(tecla):
                return funcao
        return None

    def iniciar_busca(self):
        """Inicia a busca em background e retorna imediatamente para a UI."""
        if not self._busca_lock.acquire(blocking=False):
            return {"iniciada": False}
        with self._state_lock:
            self._busca_state = {
                "executando": True,
                "status": "Buscando não-lidos…",
                "progresso": "Conectando ao Gmail",
                "resultado": None,
                "erro": None,
            }

        def progresso(msg):
            with self._state_lock:
                self._busca_state["progresso"] = str(msg)
                self._busca_state["status"] = str(msg)

        def trabalho():
            try:
                fn = self.buscar_novos
                if fn is None:
                    from gaia.routines.resumidor_emails import resumir_emails

                    fn = resumir_emails
                resultado = fn(on_progress=progresso)
                with self._state_lock:
                    self._busca_state.update({
                        "executando": False,
                        "status": "Concluído.",
                        "progresso": "Resumo salvo.",
                        "resultado": resultado,
                        "erro": None,
                    })
            except Exception as exc:
                with self._state_lock:
                    self._busca_state.update({
                        "executando": False,
                        "status": "Falhou.",
                        "progresso": "A busca não foi concluída.",
                        "resultado": None,
                        "erro": str(exc),
                    })
            finally:
                self._busca_lock.release()

        threading.Thread(target=trabalho, name="gaia-resumidor", daemon=True).start()
        return {"iniciada": True}

    def busca_estado(self):
        with self._state_lock:
            return dict(self._busca_state)

    def iniciar_historico(self):
        """Carrega o histórico em background para não congelar a janela."""
        if not self._historico_lock.acquire(blocking=False):
            return {"iniciada": False}
        with self._state_lock:
            self._historico_state = {
                "executando": True,
                "status": "Carregando histórico…",
                "dados": None,
                "erro": None,
            }

        def trabalho():
            try:
                fn = self.historico_fn
                if fn is None:
                    from gaia.core.historico import obter_historico_completo

                    fn = obter_historico_completo
                dados = fn()
                with self._state_lock:
                    self._historico_state = {
                        "executando": False,
                        "status": "Histórico carregado.",
                        "dados": dados,
                        "erro": None,
                    }
            except Exception as exc:
                with self._state_lock:
                    self._historico_state = {
                        "executando": False,
                        "status": "Falhou.",
                        "dados": None,
                        "erro": str(exc),
                    }
            finally:
                self._historico_lock.release()

        threading.Thread(target=trabalho, name="gaia-historico", daemon=True).start()
        return {"iniciada": True}

    def historico_estado(self):
        with self._state_lock:
            return dict(self._historico_state)

    def abrir_gmail(self, url):
        url = str(url or "")
        try:
            parsed = urlparse(url)
            permitido = parsed.scheme == "https" and parsed.hostname == "mail.google.com"
        except Exception:
            permitido = False
        if not permitido:
            return {"aberto": False, "mensagem": "Link inválido: apenas URLs do Gmail são abertas."}
        try:
            webbrowser.open(url)
        except Exception as exc:
            return {"aberto": False, "mensagem": f"Não consegui abrir o navegador: {exc}"}
        return {"aberto": True, "mensagem": ""}

    def sair(self):
        window = self.window
        if window is None:
            try:
                import webview

                window = webview.active_window()
            except Exception:
                window = None
        if window is None:
            return {"fechando": False}
        try:
            window.destroy()
        except Exception:
            return {"fechando": False}
        return {"fechando": True}

    def ler_ultimo_resumo(self):
        try:
            ultimo = carregar_ultimo_resumo()
        except Exception:
            return None
        if ultimo and ultimo.get("resumidos"):
            limpar_resumo_pendente()
        return ultimo

    def intervalo_tela(self):
        return WEBVIEW_INTERVALO_TELA

    def resumo_pendente(self):
        return bool(tem_resumo_pendente())

    def monitor_estado(self):
        """Retorna a amostra atual e o histórico usado pelos gráficos."""
        if self.monitor is None:
            return {
                "amostra": None,
                "cpu": {"valor": 0.0, "historico": [], "threshold": "green"},
                "ram": {"valor": 0.0, "historico": [], "threshold": "green", "usada": "--", "total": "--"},
                "gaia": {"cpu": 0.0, "ram_mb": 0.0},
                "status": f"aviso ≥{MONITOR_THRESHOLD_AVISO} · crítico ≥{MONITOR_THRESHOLD_CRITICO}",
            }

        amostra = self.monitor.ultima_amostra()
        if amostra is None:
            return {
                "amostra": None,
                "cpu": {"valor": 0.0, "historico": [], "threshold": "green"},
                "ram": {"valor": 0.0, "historico": [], "threshold": "green", "usada": "--", "total": "--"},
                "gaia": {"cpu": 0.0, "ram_mb": 0.0},
                "status": f"aviso ≥{MONITOR_THRESHOLD_AVISO} · crítico ≥{MONITOR_THRESHOLD_CRITICO}",
            }

        cpu = float(amostra.get("cpu_percent", 0.0))
        ram = float(amostra.get("ram_percent", 0.0))
        gaia_cpu = float(amostra.get("gaia_cpu_percent", 0.0))
        gaia_ram = float(amostra.get("gaia_ram_mb", 0.0))
        usada_bytes = int(amostra.get("ram_usada_bytes", 0))
        total_bytes = int(amostra.get("ram_total_bytes", 0))

        return {
            "amostra": amostra,
            "cpu": {
                "valor": cpu,
                "historico": list(self.monitor.historico_cpu(MONITOR_JANELA_SPARKLINE)),
                "threshold": _threshold(cpu),
            },
            "ram": {
                "valor": ram,
                "historico": list(self.monitor.historico_ram(MONITOR_JANELA_SPARKLINE)),
                "threshold": _threshold(ram),
                "usada": _fmt_bytes(usada_bytes),
                "total": _fmt_bytes(total_bytes),
            },
            "gaia": {"cpu": gaia_cpu, "ram_mb": gaia_ram},
            "status": f"aviso ≥{MONITOR_THRESHOLD_AVISO} · crítico ≥{MONITOR_THRESHOLD_CRITICO}",
        }


class GaiaWebviewApp:
    """Janela GAIA e sua ponte Python ↔ JavaScript."""

    def __init__(self, bridge, window, webview_module):
        self.bridge = bridge
        self.window = window
        self.bridge.window = window
        self._webview = webview_module

    def run(self):
        if platform.system() == "Linux":
            self._webview.start(gui="qt", func=_aguardar_e_instalar_patch_exit_qt)
        else:
            self._webview.start()


def criar_app_pywebview(monitor=None, rotinas=None):
    """Cria a janela PyWebview do GAIA; o GUI loop só começa em ``run()``."""
    import webview

    bridge = GaiaBridge(monitor=monitor, rotinas=rotinas)
    window = webview.create_window(
        WEBVIEW_TITULO,
        url=str(ASSETS / "index.html"),
        js_api=bridge,
        width=WEBVIEW_LARGURA,
        height=WEBVIEW_ALTURA,
        min_size=(720, 480),
        background_color="#0B1020",
    )
    return GaiaWebviewApp(bridge=bridge, window=window, webview_module=webview)
