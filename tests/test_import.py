import subprocess
import sys
from pathlib import Path


def test_main_importavel_sem_bloquear_no_menu():
    """main deve ser importável sem disparar o menu interativo."""
    resultado = subprocess.run(
        [sys.executable, "-c", "import main"],
        cwd=Path(__file__).resolve().parents[1],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert resultado.returncode == 0, resultado.stderr
