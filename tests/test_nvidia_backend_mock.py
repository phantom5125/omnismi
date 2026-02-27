"""NVIDIA backend tests with mocked pynvml bindings."""

from __future__ import annotations

from types import SimpleNamespace

from omnismi.backends.nvidia import NvidiaBackend


class _FakeNVML:
    NVML_TEMPERATURE_GPU = 0
    NVML_CLOCK_SM = 1
    NVML_CLOCK_MEM = 2

    def __init__(self) -> None:
        self.shutdown_called = False
        self.utilization_calls = 0

    def nvmlInit(self) -> None:
        return None

    def nvmlShutdown(self) -> None:
        self.shutdown_called = True

    def nvmlDeviceGetCount(self) -> int:
        return 1

    def nvmlDeviceGetHandleByIndex(self, index: int) -> str:
        assert index == 0
        return "handle-0"

    def nvmlDeviceGetName(self, handle: str) -> bytes:
        assert handle == "handle-0"
        return b"NVIDIA H100"

    def nvmlDeviceGetUUID(self, handle: str) -> str:
        return "GPU-123"

    def nvmlSystemGetDriverVersion(self) -> bytes:
        return b"550.54"

    def nvmlDeviceGetMemoryInfo(self, handle: str):
        return SimpleNamespace(total=80 * 1024**3, used=4 * 1024**3)

    def nvmlDeviceGetUtilizationRates(self, handle: str):
        self.utilization_calls += 1
        return SimpleNamespace(gpu=77)

    def nvmlDeviceGetTemperature(self, handle: str, sensor: int) -> int:
        return 64

    def nvmlDeviceGetPowerUsage(self, handle: str) -> int:
        return 275000

    def nvmlDeviceGetClockInfo(self, handle: str, clock_type: int) -> int:
        return 1410 if clock_type == self.NVML_CLOCK_SM else 1593


def test_nvidia_backend_reads_expected_fields(monkeypatch) -> None:
    fake_nvml = _FakeNVML()
    monkeypatch.setitem(__import__("sys").modules, "pynvml", fake_nvml)

    backend = NvidiaBackend()
    assert backend.available() is True

    devices = backend.devices()
    assert len(devices) == 1

    info = backend.info(devices[0], index=0)
    assert info.vendor == "nvidia"
    assert info.name == "NVIDIA H100"
    assert info.driver == "550.54"
    assert info.memory_total_bytes == 80 * 1024**3

    metrics = backend.metrics(devices[0], index=0)
    assert metrics.utilization_percent == 77.0
    assert metrics.memory_used_bytes == 4 * 1024**3
    assert metrics.temperature_c == 64.0
    assert metrics.power_w == 275.0
    assert metrics.core_clock_mhz == 1410.0
    assert metrics.memory_clock_mhz == 1593.0

    backend.close()
    assert fake_nvml.shutdown_called is True


def test_nvidia_backend_metrics_cache_and_realtime_mode(monkeypatch) -> None:
    fake_nvml = _FakeNVML()
    monkeypatch.setitem(__import__("sys").modules, "pynvml", fake_nvml)

    backend = NvidiaBackend(sample_interval_s=60.0)
    devices = backend.devices()
    assert len(devices) == 1

    _ = backend.metrics(devices[0], index=0)
    _ = backend.metrics(devices[0], index=0)
    assert fake_nvml.utilization_calls == 1

    with backend.realtime_mode():
        _ = backend.metrics(devices[0], index=0)
        _ = backend.metrics(devices[0], index=0)
    assert fake_nvml.utilization_calls == 3

    _ = backend.metrics(devices[0], index=0)
    assert fake_nvml.utilization_calls == 3

    backend.close()
