def test_get_proc_real_reutiliza_process_para_cpu_nao_zerar(monkeypatch):
    import gaia.core.monitor as monitor

    class FakeProc:
        def __init__(self):
            self.calls = 0

        def cpu_percent(self, interval=None):
            self.calls += 1
            return 0.0 if self.calls == 1 else 7.5

        def memory_info(self):
            class Info:
                rss = 10 * 1024 * 1024
            return Info()

    criado = []

    import psutil
    monkeypatch.setattr(psutil, "Process", lambda: criado.append(FakeProc()) or criado[-1])
    monkeypatch.setattr(psutil, "cpu_count", lambda logical=True: 1)

    monitor._proc_cache = None
    monitor._get_proc_real()
    segundo = monitor._get_proc_real()
    assert segundo["cpu_percent"] == 7.5
