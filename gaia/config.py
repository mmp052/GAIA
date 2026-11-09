N_FRASES_RESUMO = 3

# Monitoramento em tempo real (Essencial: CPU + RAM + GAIA)
MONITOR_INTERVALO_TELA = 1.0  # s — refresh do painel na tela principal
MONITOR_INTERVALO_FUNDO = 2.0  # s — coleta em background + escrita JSONL
MONITOR_THRESHOLD_AVISO = 80  # % — amarelo (só visual)
MONITOR_THRESHOLD_CRITICO = 90  # % — vermelho (só visual)
MONITOR_JANELA_SPARKLINE = 30  # últimos N pontos desenhados na sparkline
MONITOR_ARQUIVO_HISTORICO = "monitor_historico.jsonl"
MONITOR_ARQUIVO_ROTINAS = "monitor_rotinas.jsonl"
