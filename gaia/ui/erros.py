import traceback


def exibir_traceback(console, erro=None, contexto=None):
    if contexto:
        console.print(f"[red]Erro em {contexto}[/red]")
    if erro is not None:
        tb = "".join(traceback.format_exception(type(erro), erro, erro.__traceback__))
        console.print(tb, markup=False)
    else:
        console.print_exception()
