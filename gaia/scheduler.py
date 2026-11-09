import threading
import traceback
from datetime import datetime


def executar_com_traceback(tarefa):
    try:
        return tarefa()
    except Exception:
        traceback.print_exc()


def deve_disparar(agora_hora, ultima_execucao, hora_alvo=6, minuto_alvo=0):
    h, m = agora_hora
    if (h, m) != (hora_alvo, minuto_alvo):
        return False
    if ultima_execucao is not None and ultima_execucao == (h, m):
        return False
    return True


class Scheduler:
    def __init__(self, tarefa, hora=6, minuto=0, intervalo=60):
        self.tarefa = tarefa
        self.hora = hora
        self.minuto = minuto
        self.intervalo = intervalo
        self._stop = threading.Event()
        self._thread = None
        self._ultima_data = None
        self._lock = threading.Lock()

    def _loop(self):
        import time

        while not self._stop.wait(timeout=min(5, self.intervalo)):
            agora = datetime.now()
            hoje = agora.date()
            with self._lock:
                if self._ultima_data == hoje:
                    continue
                if (agora.hour, agora.minute) == (self.hora, self.minuto):
                    self._ultima_data = hoje
                    executar_com_traceback(self.tarefa)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self._thread

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
