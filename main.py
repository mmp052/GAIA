"""GAIA - Gestão e Assistência com Inteligência Artificial.

Entrypoint PyWebview: cria a janela desktop, inicia o monitor e o scheduler
daemon. A interface visual vive em `gaia/ui/web/` e a ponte Python ↔ JS em
`gaia/ui/webview_app.py`.

Re-exporta utilitários historicamente usados pelos testes.
"""

import gc

from gaia.config import MONITOR_INTERVALO_FUNDO, N_FRASES_RESUMO
from gaia.core.blacklist import carregar_lista_negra, esta_bloqueado, extrair_email, salvar_lista_negra
from gaia.core.email_extract import (
    _coletar_textos,
    decodificar_base64url,
    extrair_texto_email,
    limpar_html,
    limpar_texto,
    link_email,
    obter_header,
)
from gaia.core.nlp import _garantir_recursos_nltk, detectar_idioma, gerar_resumo_extrativo
from gaia.scheduler import Scheduler
from gaia.routines.resumidor_emails import resumir_emails as _resumir_emails_impl

__all__ = [
    "N_FRASES_RESUMO",
    "carregar_lista_negra",
    "salvar_lista_negra",
    "extrair_email",
    "esta_bloqueado",
    "obter_header",
    "decodificar_base64url",
    "_coletar_textos",
    "limpar_html",
    "extrair_texto_email",
    "limpar_texto",
    "detectar_idioma",
    "gerar_resumo_extrativo",
    "link_email",
    "_garantir_recursos_nltk",
    "resumir_emails",
]


def criar_monitor():
    from gaia.core.monitor import Monitor, coletar_metricas
    from gaia.core.storage import anexar_monitor_amostra

    return Monitor(
        coleta_fn=lambda: coletar_metricas(),
        salvar_fn=lambda amostra: anexar_monitor_amostra(amostra),
        intervalo=MONITOR_INTERVALO_FUNDO,
    )


def resumir_emails():
    """Executa o resumidor (usado pela compatibilidade de API)."""
    from gaia.core.monitor import medir_rotina

    @medir_rotina("resumir_emails")
    def _chamar():
        return _resumir_emails_impl()

    return _chamar()


def resumir_emails_dashboard(on_progress=None):
    """Versão para a UI: não interage com o terminal e aceita progresso."""
    from gaia.core.monitor import medir_rotina

    @medir_rotina("resumir_emails")
    def _chamar():
        return _resumir_emails_impl(on_progress=on_progress)

    return _chamar()


def historico_dashboard(on_progress=None):
    """Versão para a UI: retorna o histórico estruturado, sem imprimir."""
    from gaia.core.historico import obter_historico_completo

    if on_progress is not None:
        try:
            on_progress("Lendo histórico (hoje+ontem)...")
        except Exception:
            pass
    resultado = obter_historico_completo()
    if on_progress is not None:
        try:
            total = (resultado.get("resumo") or {}).get("total", 0)
            on_progress(f"Histórico carregado — {total} amostras")
        except Exception:
            pass
    return resultado


def criar_app_pywebview(monitor=None):
    """Cria a janela PyWebview (wiring fino; o GUI loop começa em run())."""
    from gaia.ui.webview_app import criar_app_pywebview as _criar_app

    if monitor is None:
        monitor = criar_monitor()
    rotinas = [
        ("1", "Resumidor de Emails", resumir_emails_dashboard),
        ("2", "Histórico", historico_dashboard),
    ]
    return _criar_app(monitor=monitor, rotinas=rotinas)


def executar_pywebview():
    """Executa GAIA: monitor + scheduler + janela nativa."""
    scheduler = Scheduler(tarefa=criar_tarefa_scheduler(), hora=6, minuto=0)
    scheduler.start()
    monitor = criar_monitor()
    monitor.iniciar()
    try:
        app = criar_app_pywebview(monitor=monitor)
        app.run()
    finally:
        try:
            monitor.parar()
        except Exception:
            pass
        scheduler.stop()
        gc.collect()


def criar_tarefa_scheduler():
    from gaia.core.monitor import medir_rotina

    @medir_rotina("resumir_emails")
    def tarefa():
        return _resumir_emails_impl()

    return tarefa


def main():
    """Entrypoint principal — abre a janela PyWebview."""
    executar_pywebview()


if __name__ == "__main__":
    main()
