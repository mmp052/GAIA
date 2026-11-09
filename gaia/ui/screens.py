def exibir_menu(console, menu):
    console.clear()
    for tecla, (titulo, _) in menu.itens():
        console.print(f"{tecla} - {titulo}")
    console.print("")


def exibir_cabecalho_rotina(console, titulo):
    from rich.panel import Panel

    console.clear()
    console.print(Panel(f"[bold]{titulo}[/bold] — Processando...", border_style="blue"))


def exibir_resultado_final(console, resultado):
    from rich.panel import Panel

    console.clear()
    dia = resultado.get("dia") if resultado else None
    resumidos = resultado.get("resumidos", []) if resultado else []
    ignorados = resultado.get("ignorados", []) if resultado else []
    falhas = resultado.get("falhas", []) if resultado else []
    corpo = f"Dia: {dia}\nResumidos: {len(resumidos)} · Ignorados: {len(ignorados)} · Falhas: {len(falhas)}"
    if resultado and resultado.get("arquivo"):
        corpo += f"\nJSON: {resultado['arquivo']}"
    console.print(Panel(corpo, title="Resultado", border_style="blue"))


def exibir_paginado(console, blocos, por_pagina=5, entrada=None):
    if entrada is None:
        entrada = input
    total = len(blocos)
    for inicio in range(0, total, por_pagina):
        fim = min(inicio + por_pagina, total)
        for bloco in blocos[inicio:fim]:
            if isinstance(bloco, (list, tuple)):
                for item in bloco:
                    console.print(item)
            else:
                console.print(bloco)
        if fim < total:
            console.print(f"\nPágina {inicio // por_pagina + 1}/{(total + por_pagina - 1) // por_pagina} — {fim}/{total}")
            try:
                entrada("Pressione Enter para próxima página... ")
            except EOFError:
                break
