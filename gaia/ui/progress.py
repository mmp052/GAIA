from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn


def criar_progress(console):
    return Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def criar_status(console, texto="Carregando..."):
    from rich.status import Status

    return Status(texto, console=console, spinner="dots")
