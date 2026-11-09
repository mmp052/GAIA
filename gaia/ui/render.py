from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def texto_link_email(link):
    txt = Text("▶ Ler email completo", style=f"link {link}")
    txt.style = f"underline cyan link {link}"
    return txt


def render_tabela_busca(busca, data_alvo):
    table = Table(title="Busca do dia mais recente com não-lidos", show_header=True)
    table.add_column("Data")
    table.add_column("Não-lidos", justify="right")
    for dia_str, qtd in busca:
        style = "bold green" if qtd else None
        table.add_row(dia_str, str(qtd), style=style)
        if dia_str == data_alvo:
            break
    return table


def render_painel_resumo(remetente, assunto, data, resumo, idioma):
    linhas = [
        f"[bold]{escape(assunto) or '(sem assunto)'}[/bold]",
        f"[dim]{escape(data)}[/dim]",
        "",
        f"[bold]Resumo ({idioma}):[/bold] {escape(resumo)}",
        "",
    ]
    titulo = f"{remetente}"
    return Panel("\n".join(linhas).rstrip(), title=escape(titulo)[:80], border_style="blue")
