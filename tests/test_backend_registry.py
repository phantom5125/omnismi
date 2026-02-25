"""Backend registry behavior tests."""

from __future__ import annotations

import time

from omnismi.backends.base import BaseBackend
from omnismi.backends.registry import active_backends, close_all, registered_backends
from omnismi.models import GPUMetrics, GPUInfo


class _UnavailableBackend(BaseBackend):
    vendor = "nvidia"

    def available(self) -> bool:
        return False

    def devices(self) -> list[object]:
        return []

    def info(self, device: object, index: int) -> GPUInfo:
        raise AssertionError("not expected")

    def metrics(self, device: object, index: int) -> GPUMetrics:
        raise AssertionError("not expected")


class _AvailableBackend(BaseBackend):
    vendor = "amd"

    def __init__(self) -> None:
        self.closed = False

    def available(self) -> bool:
        return True

    def devices(self) -> list[object]:
        return ["h0"]

    def info(self, device: object, index: int) -> GPUInfo:
        return GPUInfo(index=index, vendor="amd", name="MI300X", uuid=None, driver=None, memory_total_bytes=None)

    def metrics(self, device: object, index: int) -> GPUMetrics:
        return GPUMetrics(
            index=index,
            utilization_percent=None,
            memory_used_bytes=None,
            memory_total_bytes=None,
            temperature_c=None,
            power_w=None,
            core_clock_mhz=None,
            memory_clock_mhz=None,
            timestamp_ns=time.time_ns(),
        )

    def close(self) -> None:
        self.closed = True


def test_active_backends_filters_unavailable(backend_factories) -> None:
    backend_factories([_UnavailableBackend, _AvailableBackend])

    active = active_backends()
    assert len(active) == 1
    assert active[0].vendor == "amd"


def test_close_all_closes_registered_backends(backend_factories) -> None:
    backend_factories([_AvailableBackend])

    backends = registered_backends()
    assert len(backends) == 1
    backend = backends[0]

    close_all()
    assert isinstance(backend, _AvailableBackend)
    assert backend.closed is True
