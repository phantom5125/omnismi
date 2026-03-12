"""Google TPU backend tests with mocked libtpu monitoring bindings."""

from __future__ import annotations

import sys
from types import ModuleType

from omnismi.backends.google_tpu import GoogleTpuBackend


class _FakeMetric:
    def __init__(self, values):
        self._values = list(values)

    def data(self):
        return list(self._values)


class _FakeTPUMonitoring(ModuleType):
    def __init__(self) -> None:
        super().__init__("libtpu.sdk.tpumonitoring")
        self._metrics = {
            "duty_cycle_pct": _FakeMetric(["90", "75.5"]),
            "hbm_capacity_total": _FakeMetric([16 * 1024**3, 16 * 1024**3]),
            "hbm_capacity_usage": _FakeMetric([4 * 1024**3, 6 * 1024**3]),
        }

    def list_supported_metrics(self):
        return list(self._metrics.keys())

    def get_metric(self, name):
        return self._metrics.get(name)


def _install_fake_libtpu(monkeypatch) -> None:
    tpumonitoring = _FakeTPUMonitoring()

    sdk_module = ModuleType("libtpu.sdk")
    sdk_module.tpumonitoring = tpumonitoring

    libtpu_module = ModuleType("libtpu")
    libtpu_module.__version__ = "0.0.37"
    libtpu_module.sdk = sdk_module

    monkeypatch.setitem(sys.modules, "libtpu", libtpu_module)
    monkeypatch.setitem(sys.modules, "libtpu.sdk", sdk_module)
    monkeypatch.setitem(sys.modules, "libtpu.sdk.tpumonitoring", tpumonitoring)


def test_google_tpu_backend_reads_expected_fields(monkeypatch) -> None:
    _install_fake_libtpu(monkeypatch)
    monkeypatch.setenv("TPU_ACCELERATOR_TYPE", "v5e")

    backend = GoogleTpuBackend()
    assert backend.available() is True

    devices = backend.devices()
    assert devices == [0, 1]

    info = backend.info(devices[0], index=0)
    assert info.vendor == "google"
    assert info.name == "v5e"
    assert info.driver == "0.0.37"
    assert info.memory_total_bytes == 16 * 1024**3

    metrics = backend.metrics(devices[1], index=1)
    assert metrics.utilization_percent == 75.5
    assert metrics.memory_used_bytes == 6 * 1024**3
    assert metrics.memory_total_bytes == 16 * 1024**3
    assert metrics.temperature_c is None
    assert metrics.power_w is None


def test_google_tpu_backend_is_unavailable_without_metrics(monkeypatch) -> None:
    tpumonitoring = _FakeTPUMonitoring()
    tpumonitoring._metrics = {}

    sdk_module = ModuleType("libtpu.sdk")
    sdk_module.tpumonitoring = tpumonitoring

    libtpu_module = ModuleType("libtpu")
    libtpu_module.__version__ = "0.0.37"
    libtpu_module.sdk = sdk_module

    monkeypatch.setitem(sys.modules, "libtpu", libtpu_module)
    monkeypatch.setitem(sys.modules, "libtpu.sdk", sdk_module)
    monkeypatch.setitem(sys.modules, "libtpu.sdk.tpumonitoring", tpumonitoring)

    backend = GoogleTpuBackend()
    assert backend.available() is False
    assert backend.devices() == []
