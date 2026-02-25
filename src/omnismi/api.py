"""Public Omnismi API."""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from omnismi.backends.base import BaseBackend
from omnismi.backends.registry import active_backends
from omnismi.models import GPUMetrics, GPUInfo


class GPU:
    """Lightweight GPU object with psutil-style read methods."""

    __slots__ = ("_backend", "_device", "_index")

    def __init__(self, backend: BaseBackend, device: Any, index: int) -> None:
        self._backend = backend
        self._device = device
        self._index = index

    @property
    def index(self) -> int:
        """Global Omnismi GPU index."""
        return self._index

    def info(self) -> GPUInfo:
        """Return static information for this GPU."""
        try:
            info = self._backend.info(self._device, self._index)
            if info.index != self._index:
                info = replace(info, index=self._index)
            return info
        except Exception:
            return GPUInfo(
                index=self._index,
                vendor=self._backend.vendor,
                name=f"{self._backend.vendor.upper()} GPU {self._index}",
                uuid=None,
                driver=None,
                memory_total_bytes=None,
            )

    def metrics(self) -> GPUMetrics:
        """Return current metrics for this GPU."""
        try:
            metrics = self._backend.metrics(self._device, self._index)
            if metrics.index != self._index:
                metrics = replace(metrics, index=self._index)
            return metrics
        except Exception:
            return GPUMetrics(
                index=self._index,
                utilization_percent=None,
                memory_used_bytes=None,
                memory_total_bytes=None,
                temperature_c=None,
                power_w=None,
                core_clock_mhz=None,
                memory_clock_mhz=None,
                timestamp_ns=time.time_ns(),
            )

    def __repr__(self) -> str:
        return f"GPU(index={self._index}, vendor={self._backend.vendor!r})"


def gpus() -> list[GPU]:
    """Return all currently visible GPUs across all active backends."""
    devices: list[GPU] = []
    next_index = 0

    for backend in active_backends():
        try:
            backend_devices = backend.devices()
        except Exception:
            continue

        for device in backend_devices:
            devices.append(GPU(backend=backend, device=device, index=next_index))
            next_index += 1

    return devices


def count() -> int:
    """Return the number of currently visible GPUs."""
    return len(gpus())


def gpu(index: int) -> GPU | None:
    """Return a single GPU by global index, or None if out of range."""
    if index < 0:
        return None

    for device in gpus():
        if device.index == index:
            return device
    return None
