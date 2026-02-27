"""NVIDIA backend powered by nvidia-ml-py (pynvml module)."""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import replace
from typing import Any

from omnismi.backends.base import BaseBackend
from omnismi.models import GPUMetrics, GPUInfo
from omnismi.normalize import (
    normalize_bytes,
    normalize_clock_mhz,
    normalize_percent,
    normalize_power_w,
    normalize_temperature_c,
    normalize_text,
    normalize_uuid,
)


class NvidiaBackend(BaseBackend):
    """Query NVIDIA GPUs via NVML."""

    vendor = "nvidia"

    def __init__(self, sample_interval_s: float = 0.5) -> None:
        self._nvml: Any | None = None
        self._import_failed = False
        self._initialized = False
        self._sample_interval_s = max(0.1, float(sample_interval_s))
        self._metrics_cache: dict[int, GPUMetrics] = {}
        self._cache_lock = threading.Lock()
        self._sampler_thread: threading.Thread | None = None
        self._sampler_stop_event: threading.Event | None = None
        self._realtime_mode_depth = 0

    def _import_nvml(self) -> bool:
        if self._nvml is not None:
            return True
        if self._import_failed:
            return False
        try:
            import pynvml as nvml  # type: ignore

            self._nvml = nvml
            return True
        except Exception:
            self._import_failed = True
            return False

    def _ensure_initialized(self) -> bool:
        if not self._import_nvml():
            return False
        if self._initialized:
            return True

        assert self._nvml is not None
        try:
            self._nvml.nvmlInit()
        except Exception as exc:  # pragma: no cover - depends on local NVML state
            if exc.__class__.__name__ != "NVMLError_AlreadyInitialized":
                return False
        self._initialized = True
        return True

    def _decode_text(self, value: Any) -> str | None:
        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8", errors="replace")
            except Exception:
                return None
        return normalize_text(value)

    def available(self) -> bool:
        if not self._ensure_initialized():
            return False

        assert self._nvml is not None
        try:
            return self._nvml.nvmlDeviceGetCount() > 0
        except Exception:
            return False

    def devices(self) -> list[Any]:
        if not self._ensure_initialized():
            return []

        assert self._nvml is not None
        handles: list[Any] = []
        try:
            count = self._nvml.nvmlDeviceGetCount()
        except Exception:
            return []

        for vendor_index in range(count):
            try:
                handle = self._nvml.nvmlDeviceGetHandleByIndex(vendor_index)
                handles.append((vendor_index, handle))
            except Exception:
                continue
        return handles

    def info(self, device: Any, index: int) -> GPUInfo:
        vendor_index, handle = device
        driver = None
        name = f"NVIDIA GPU {vendor_index}"
        uuid = None
        memory_total = None

        assert self._nvml is not None
        try:
            name = self._decode_text(self._nvml.nvmlDeviceGetName(handle)) or name
        except Exception:
            pass

        try:
            uuid = normalize_uuid(self._nvml.nvmlDeviceGetUUID(handle))
        except Exception:
            pass

        try:
            driver = self._decode_text(self._nvml.nvmlSystemGetDriverVersion())
        except Exception:
            pass

        try:
            memory_info = self._nvml.nvmlDeviceGetMemoryInfo(handle)
            memory_total = normalize_bytes(memory_info.total)
        except Exception:
            pass

        return GPUInfo(
            index=index,
            vendor=self.vendor,
            name=name,
            uuid=uuid,
            driver=driver,
            memory_total_bytes=memory_total,
        )

    def metrics(self, device: Any, index: int) -> GPUMetrics:
        if not self._ensure_initialized():
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

        vendor_index, handle = device

        if self._is_realtime_mode():
            sample = self._collect_metrics_for_handle(vendor_index, handle)
            self._store_cached_metrics(vendor_index, sample)
            return replace(sample, index=index) if sample.index != index else sample

        cached = self._cached_metrics(vendor_index)
        if cached is not None:
            return replace(cached, index=index) if cached.index != index else cached

        sample = self._collect_metrics_for_handle(vendor_index, handle)
        self._store_cached_metrics(vendor_index, sample)
        self._ensure_sampler_running()
        return replace(sample, index=index) if sample.index != index else sample

    def _collect_metrics_for_handle(self, vendor_index: int, handle: Any) -> GPUMetrics:
        timestamp_ns = time.time_ns()

        utilization = None
        memory_used = None
        memory_total = None
        temperature = None
        power_w = None
        core_clock = None
        memory_clock = None

        assert self._nvml is not None

        try:
            util = self._nvml.nvmlDeviceGetUtilizationRates(handle)
            utilization = normalize_percent(util.gpu)
        except Exception:
            pass

        try:
            memory_info = self._nvml.nvmlDeviceGetMemoryInfo(handle)
            memory_used = normalize_bytes(memory_info.used)
            memory_total = normalize_bytes(memory_info.total)
        except Exception:
            pass

        try:
            temperature = normalize_temperature_c(
                self._nvml.nvmlDeviceGetTemperature(handle, self._nvml.NVML_TEMPERATURE_GPU),
                unit="auto",
            )
        except Exception:
            pass

        try:
            power_w = normalize_power_w(self._nvml.nvmlDeviceGetPowerUsage(handle), unit="mw")
        except Exception:
            pass

        try:
            core_clock = normalize_clock_mhz(
                self._nvml.nvmlDeviceGetClockInfo(handle, self._nvml.NVML_CLOCK_SM)
            )
        except Exception:
            pass

        try:
            memory_clock = normalize_clock_mhz(
                self._nvml.nvmlDeviceGetClockInfo(handle, self._nvml.NVML_CLOCK_MEM)
            )
        except Exception:
            pass

        return GPUMetrics(
            index=vendor_index,
            utilization_percent=utilization,
            memory_used_bytes=memory_used,
            memory_total_bytes=memory_total,
            temperature_c=temperature,
            power_w=power_w,
            core_clock_mhz=core_clock,
            memory_clock_mhz=memory_clock,
            timestamp_ns=timestamp_ns,
        )

    def _cached_metrics(self, vendor_index: int) -> GPUMetrics | None:
        with self._cache_lock:
            return self._metrics_cache.get(vendor_index)

    def _store_cached_metrics(self, vendor_index: int, metrics: GPUMetrics) -> None:
        with self._cache_lock:
            self._metrics_cache[vendor_index] = metrics

    def _is_realtime_mode(self) -> bool:
        with self._cache_lock:
            return self._realtime_mode_depth > 0

    def _ensure_sampler_running(self) -> None:
        with self._cache_lock:
            if self._sampler_thread is not None and self._sampler_thread.is_alive():
                return

            stop_event = threading.Event()
            thread = threading.Thread(
                target=self._sampler_loop,
                args=(stop_event,),
                name="omnismi-nvml-sampler",
                daemon=True,
            )
            self._sampler_stop_event = stop_event
            self._sampler_thread = thread

        thread.start()

    def _sampler_loop(self, stop_event: threading.Event) -> None:
        while not stop_event.wait(self._sample_interval_s):
            self._collect_all_metrics_once()

    def _collect_all_metrics_once(self) -> None:
        if not self._initialized or self._nvml is None:
            return

        try:
            count = self._nvml.nvmlDeviceGetCount()
        except Exception:
            return

        for vendor_index in range(count):
            try:
                handle = self._nvml.nvmlDeviceGetHandleByIndex(vendor_index)
                sample = self._collect_metrics_for_handle(vendor_index, handle)
                self._store_cached_metrics(vendor_index, sample)
            except Exception:
                continue

    @contextmanager
    def realtime_mode(self):
        with self._cache_lock:
            self._realtime_mode_depth += 1
        try:
            yield
        finally:
            with self._cache_lock:
                if self._realtime_mode_depth > 0:
                    self._realtime_mode_depth -= 1

    def _stop_sampler(self) -> None:
        thread: threading.Thread | None = None
        stop_event: threading.Event | None = None

        with self._cache_lock:
            thread = self._sampler_thread
            stop_event = self._sampler_stop_event
            self._sampler_thread = None
            self._sampler_stop_event = None
            self._metrics_cache.clear()

        if stop_event is not None:
            stop_event.set()
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def close(self) -> None:
        self._stop_sampler()
        if not self._initialized or self._nvml is None:
            return
        try:
            self._nvml.nvmlShutdown()
        except Exception:
            pass
        self._initialized = False
