"""Google TPU backend powered by libtpu monitoring."""

from __future__ import annotations

import os
import time
from typing import Any, Callable

from omnismi.backends.base import BaseBackend
from omnismi.models import GPUMetrics, GPUInfo
from omnismi.normalize import normalize_bytes, normalize_percent, normalize_text

_COUNT_METRICS = ("duty_cycle_pct", "hbm_capacity_total", "hbm_capacity_usage")
_UTILIZATION_METRICS = ("duty_cycle_pct",)
_MEMORY_TOTAL_METRICS = ("hbm_capacity_total",)
_MEMORY_USED_METRICS = ("hbm_capacity_usage",)
_NAME_ENV_VARS = ("TPU_ACCELERATOR_TYPE", "ACCELERATOR_TYPE")


class GoogleTpuBackend(BaseBackend):
    """Query Google TPUs via the libtpu monitoring SDK."""

    vendor = "google"

    def __init__(self) -> None:
        self._libtpu: Any | None = None
        self._tpumonitoring: Any | None = None
        self._import_failed = False
        self._supported_metrics: set[str] | None = None

    def _import_tpumonitoring(self) -> bool:
        if self._libtpu is not None and self._tpumonitoring is not None:
            return True
        if self._import_failed:
            return False

        try:
            import libtpu  # type: ignore
            from libtpu.sdk import tpumonitoring  # type: ignore

            self._libtpu = libtpu
            self._tpumonitoring = tpumonitoring
            return True
        except Exception:
            self._import_failed = True
            return False

    def _metric_names(self) -> set[str]:
        if not self._import_tpumonitoring():
            return set()
        if self._supported_metrics is None:
            try:
                names = self._tpumonitoring.list_supported_metrics()
                self._supported_metrics = {str(name) for name in names or []}
            except Exception:
                self._supported_metrics = set()
        return self._supported_metrics

    def _metric_data(self, metric_name: str) -> list[Any]:
        if metric_name not in self._metric_names():
            return []

        assert self._tpumonitoring is not None
        try:
            metric = self._tpumonitoring.get_metric(metric_name)
            if metric is None:
                return []
            data = metric.data()
        except Exception:
            return []

        if data is None:
            return []
        if isinstance(data, (list, tuple)):
            return list(data)
        return [data]

    def _device_count(self) -> int:
        count = 0
        for metric_name in _COUNT_METRICS:
            count = max(count, len(self._metric_data(metric_name)))
        return count

    def available(self) -> bool:
        return self._device_count() > 0

    def devices(self) -> list[Any]:
        return list(range(self._device_count()))

    def _device_name(self) -> str:
        for env_var in _NAME_ENV_VARS:
            value = normalize_text(os.environ.get(env_var))
            if value is not None:
                return value
        return "Google TPU"

    def _metric_value(
        self,
        metric_names: tuple[str, ...],
        index: int,
        normalizer: Callable[[Any], Any],
    ) -> Any:
        for metric_name in metric_names:
            data = self._metric_data(metric_name)
            if index >= len(data):
                continue
            value = normalizer(data[index])
            if value is not None:
                return value
        return None

    def info(self, device: Any, index: int) -> GPUInfo:
        driver = normalize_text(getattr(self._libtpu, "__version__", None))
        memory_total = self._metric_value(_MEMORY_TOTAL_METRICS, int(device), normalize_bytes)

        return GPUInfo(
            index=index,
            vendor=self.vendor,
            name=self._device_name(),
            uuid=None,
            driver=driver,
            memory_total_bytes=memory_total,
        )

    def metrics(self, device: Any, index: int) -> GPUMetrics:
        device_index = int(device)

        return GPUMetrics(
            index=index,
            utilization_percent=self._metric_value(
                _UTILIZATION_METRICS, device_index, normalize_percent
            ),
            memory_used_bytes=self._metric_value(
                _MEMORY_USED_METRICS, device_index, normalize_bytes
            ),
            memory_total_bytes=self._metric_value(
                _MEMORY_TOTAL_METRICS, device_index, normalize_bytes
            ),
            temperature_c=None,
            power_w=None,
            core_clock_mhz=None,
            memory_clock_mhz=None,
            timestamp_ns=time.time_ns(),
        )
