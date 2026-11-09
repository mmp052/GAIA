"""Monitoramento em tempo real — núcleo (coleta pura, testável com fakes).

Essencial: CPU total, RAM total e o próprio GAIA. Sem lista de processos.
Coleta via `psutil` (import tardio) para não quebrar testes offline.
"""

from datetime import datetime


def _get_cpu_real():
    import psutil

    return psutil.cpu_percent(interval=None)


def _get_mem_real():
    import psutil

    mem = psutil.virtual_memory()
    return {
        "percent": float(mem.percent),
        "used_bytes": int(mem.used),
        "total_bytes": int(mem.total),
        "available_bytes": int(mem.available),
    }


def _get_proc_real():
    import psutil

    proc = psutil.Process()
    return {
        "cpu_percent": float(proc.cpu_percent(interval=None)),
        "memory_mb": float(proc.memory_info().rss / 1024 / 1024),
    }


import collections
import threading


class Monitor:
    """Buffer thread-safe + sampler em background.

    - `registrar(amostra)`: anexa amostra ao buffer (chamado pelo sampler).
    - `ultima_amostra()`, `ultimas_amostras(n)`, `historico_cpu/ram(n)`: leitura para UI.
    - `iniciar()`/`parar()`: thread daemon que coleta a cada `intervalo` segundos
      e, se `salvar_fn` for dado, persiste cada amostra (JSONL).
    """

    def __init__(self, capacidade=3600, coleta_fn=None, salvar_fn=None, intervalo=2.0):
        self._buffer = collections.deque(maxlen=capacidade)
        self._lock = threading.Lock()
        self.coleta_fn = coleta_fn
        self.salvar_fn = salvar_fn
        self.intervalo = intervalo
        self._stop = threading.Event()
        self._thread = None

    def registrar(self, amostra):
        with self._lock:
            self._buffer.append(amostra)

    def ultima_amostra(self):
        with self._lock:
            return self._buffer[-1] if self._buffer else None

    def ultimas_amostras(self, n):
        with self._lock:
            return list(self._buffer)[-n:] if n else list(self._buffer)

    def historico_cpu(self, n):
        return [a.get("cpu_percent", 0.0) for a in self.ultimas_amostras(n)]

    def historico_ram(self, n):
        return [a.get("ram_percent", 0.0) for a in self.ultimas_amostras(n)]

    def _loop(self):
        import time

        while not self._stop.wait(timeout=0):
            try:
                fn = self.coleta_fn if self.coleta_fn is not None else coletar_metricas
                amostra = fn()
            except Exception:
                amostra = None
            if amostra is not None:
                self.registrar(amostra)
                if self.salvar_fn is not None:
                    try:
                        self.salvar_fn(amostra)
                    except Exception:
                        pass
            self._stop.wait(timeout=self.intervalo)

    def iniciar(self):
        if self._thread and self._thread.is_alive():
            return self._thread
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self._thread

    def parar(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)


def coletar_metricas(get_cpu=None, get_mem=None, get_proc=None, agora=None):
    """Coleta uma amostra: CPU, RAM e GAIA. Aceita fakes para testes."""
    cpu_fn = get_cpu if get_cpu is not None else _get_cpu_real
    mem_fn = get_mem if get_mem is not None else _get_mem_real
    proc_fn = get_proc if get_proc is not None else _get_proc_real

    mem = mem_fn()
    proc = proc_fn()

    if agora is None:
        agora = datetime.now().isoformat(timespec="seconds")

    return {
        "timestamp": agora,
        "cpu_percent": float(cpu_fn()),
        "ram_percent": float(mem["percent"]),
        "ram_usada_bytes": int(mem["used_bytes"]),
        "ram_total_bytes": int(mem["total_bytes"]),
        "ram_disponivel_bytes": int(mem["available_bytes"]),
        "gaia_cpu_percent": float(proc["cpu_percent"]),
        "gaia_ram_mb": float(proc["memory_mb"]),
    }


def registrar_execucao_rotina(rotina, duracao_s, cpu_s=0.0, ram_mb=0.0, agora=None, caminho=None):
    """Grava log de uma execução de rotina (sem separar manual vs scheduler)."""
    from gaia.config import MONITOR_ARQUIVO_ROTINAS
    from gaia.core.storage import anexar_log_rotina

    if agora is None:
        agora = datetime.now().isoformat(timespec="seconds")
    registro = {
        "timestamp": agora,
        "rotina": rotina,
        "duracao_s": float(duracao_s),
        "cpu_s": float(cpu_s),
        "ram_mb": float(ram_mb),
    }
    if caminho is not None:
        anexar_log_rotina(registro, caminho=caminho)
    else:
        anexar_log_rotina(registro, caminho=MONITOR_ARQUIVO_ROTINAS)
    return registro


def _cpu_tempo_atual():
    try:
        import psutil

        return sum(psutil.Process().cpu_times()[:2])
    except Exception:
        return 0.0


def _ram_atual_mb():
    try:
        import psutil

        return psutil.Process().memory_info().rss / 1024 / 1024
    except Exception:
        return 0.0


def medir_rotina(nome):
    """Decorator: mede tempo wall + CPU/RAM delta e loga via `registrar_execucao_rotina`."""
    import functools
    import time

    def decorador(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            cpu0 = _cpu_tempo_atual()
            try:
                return fn(*args, **kwargs)
            finally:
                duracao = time.perf_counter() - t0
                cpu_s = max(0.0, _cpu_tempo_atual() - cpu0)
                ram_mb = _ram_atual_mb()
                try:
                    registrar_execucao_rotina(nome, duracao_s=duracao, cpu_s=cpu_s, ram_mb=ram_mb)
                except Exception:
                    pass

        return wrapper

    return decorador
