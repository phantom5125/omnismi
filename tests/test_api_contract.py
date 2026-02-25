"""API contract tests for Omnismi 1.0."""

from __future__ import annotations

import time

import omnismi as omi
from omnismi.backends.base import BaseBackend
from omnismi.models import GPUMetrics, GPUInfo


class _DummyBackend(BaseBackend):
    vendor = "nvidia"

    def available(self) -> bool:
        return True

    def devices(self) -> list[object]:
        return ["h0", "h1"]

    def info(self, device: object, index: int) -> GPUInfo:
        return GPUInfo(
            index=index,
            vendor="nvidia",
            name=f"GPU-{index}",
            uuid=f"uuid-{index}",
            driver="550.54",
            memory_total_bytes=80 * 1024**3,
        )

    def metrics(self, device: object, index: int) -> GPUMetrics:
        return GPUMetrics(
            index=index,
            utilization_percent=25.0,
            memory_used_bytes=4 * 1024**3,
            memory_total_bytes=80 * 1024**3,
            temperature_c=55.0,
            power_w=230.0,
            core_clock_mhz=1400.0,
            memory_clock_mhz=1593.0,
            timestamp_ns=time.time_ns(),
        )


def test_public_exports_without_get_prefix() -> None:
    assert "count" in omi.__all__
    assert "gpus" in omi.__all__
    assert "gpu" in omi.__all__
    assert all(not name.startswith("get_") for name in omi.__all__)


def test_count_gpus_and_gpu_lookup(backend_factories) -> None:
    backend_factories([_DummyBackend])

    devices = omi.gpus()
    assert len(devices) == 2
    assert omi.count() == 2
    assert omi.gpu(0) is not None
    assert omi.gpu(1) is not None
    assert omi.gpu(2) is None
    assert omi.gpu(-1) is None


def test_gpu_methods_return_models(backend_factories) -> None:
    backend_factories([_DummyBackend])

    device = omi.gpu(0)
    assert device is not None

    info = device.info()
    metrics = device.metrics()

    assert isinstance(info, GPUInfo)
    assert isinstance(metrics, GPUMetrics)
    assert info.vendor == "nvidia"
    assert metrics.utilization_percent == 25.0
