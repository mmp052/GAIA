def test_get_proc_real_normaliza_cpu_pelo_total_de_nucleos(monkeypatch):
    import gaia.core.monitor as monitor

    class FakeProc:
        def cpu_percent(self, interval=None):
            return 50.0

        def memory_info(self):
            class Info:
                rss = 10 * 1024 * 1024
            return Info()

    import psutil
    monkeypatch.setattr(psutil, "Process", lambda: FakeProc())
    monkeypatch.setattr(psutil, "cpu_count", lambda logical=True: 8)

    monitor._proc_cache = None
    resultado = monitor._get_proc_real()
    assert resultado["cpu_percent"] == 6.25
