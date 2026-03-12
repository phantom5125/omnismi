"""AMD backend powered by amdsmi."""

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


class AmdBackend(BaseBackend):
    """Query AMD GPUs via AMD SMI Python bindings."""

    vendor = "amd"

    def __init__(self, sample_interval_s: float = 0.5) -> None:
        self._amdsmi: Any | None = None
        self._import_failed = False
        self._initialized = False
        self._sample_interval_s = max(0.1, float(sample_interval_s))
        self._metrics_cache: dict[int, GPUMetrics] = {}
        self._cache_lock = threading.Lock()
        self._sampler_thread: threading.Thread | None = None
        self._sampler_stop_event: threading.Event | None = None
        self._realtime_mode_depth = 0

    def _import_amdsmi(self) -> bool:
        if self._amdsmi is not None:
            return True
        if self._import_failed:
            return False
        try:
            import amdsmi  # type: ignore

            self._amdsmi = amdsmi
            return True
        except Exception:
            self._import_failed = True
            return False

    def _ensure_initialized(self) -> bool:
        if not self._import_amdsmi():
            return False
        if self._initialized:
            return True

        assert self._amdsmi is not None
        try:
            self._amdsmi.amdsmi_init()
            self._initialized = True
            return True
        except Exception:
            return False

    def _handles(self) -> list[Any]:
        if not self._ensure_initialized():
            return []

        assert self._amdsmi is not None
        try:
            if hasattr(self._amdsmi, "amdsmi_get_processor_handles"):
                return list(self._amdsmi.amdsmi_get_processor_handles())
            if hasattr(self._amdsmi, "amdsmi_get_gpu_handles"):
                return list(self._amdsmi.amdsmi_get_gpu_handles())
        except Exception:
            return []
        return []

    def available(self) -> bool:
        return len(self._handles()) > 0

    def devices(self) -> list[Any]:
        return list(enumerate(self._handles()))

    def _asic_info(self, handle: Any) -> dict[str, Any]:
        assert self._amdsmi is not None
        if not hasattr(self._amdsmi, "amdsmi_get_gpu_asic_info"):
            return {}
        try:
            result = self._amdsmi.amdsmi_get_gpu_asic_info(handle)
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}

    def _driver_info(self, handle: Any) -> dict[str, Any]:
        assert self._amdsmi is not None
        if not hasattr(self._amdsmi, "amdsmi_get_gpu_driver_info"):
            return {}
        try:
            result = self._amdsmi.amdsmi_get_gpu_driver_info(handle)
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}

    def _vram_usage(self, handle: Any) -> dict[str, Any]:
        assert self._amdsmi is not None
        if hasattr(self._amdsmi, "amdsmi_get_gpu_vram_usage"):
            try:
                result = self._amdsmi.amdsmi_get_gpu_vram_usage(handle)
                if isinstance(result, dict):
                    return result
            except Exception:
                pass
        if hasattr(self._amdsmi, "amdsmi_get_gpu_memory_info"):
            try:
                result = self._amdsmi.amdsmi_get_gpu_memory_info(handle)
                if isinstance(result, dict):
                    return {
                        "vram_total": result.get("vram_total"),
                        "vram_used": result.get("vram_used"),
                    }
            except Exception:
                pass
        return {}

    def info(self, device: Any, index: int) -> GPUInfo:
        vendor_index, handle = device

        name = f"AMD GPU {vendor_index}"
        uuid = None
        driver = None
        memory_total = None

        asic_info = self._asic_info(handle)
        if asic_info:
            name = normalize_text(asic_info.get("market_name")) or name
            uuid = normalize_uuid(asic_info.get("asic_serial"))

        driver_info = self._driver_info(handle)
        if driver_info:
            driver = normalize_text(driver_info.get("driver_version"))

        if driver is None and hasattr(self._amdsmi, "amdsmi_get_gpu_vbios_info"):
            try:
                vbios_info = self._amdsmi.amdsmi_get_gpu_vbios_info(handle)
                if isinstance(vbios_info, dict):
                    driver = normalize_text(vbios_info.get("version") or vbios_info.get("vbios_version"))
            except Exception:
                pass

        vram_usage = self._vram_usage(handle)
        memory_total = normalize_bytes(vram_usage.get("vram_total"))

        return GPUInfo(
            index=index,
            vendor=self.vendor,
            name=name,
            uuid=uuid,
            driver=driver,
            memory_total_bytes=memory_total,
        )

    def _read_temperature(self, handle: Any) -> float | None:
        """Read temperature with fallback: EDGE -> HOTSPOT -> VRAM."""
        assert self._amdsmi is not None

        # Temperature types to try in order of preference
        temp_types = ["EDGE", "HOTSPOT", "VRAM"]

        if (
            hasattr(self._amdsmi, "amdsmi_get_temp_metric")
            and hasattr(self._amdsmi, "AmdSmiTemperatureType")
            and hasattr(self._amdsmi, "AmdSmiTemperatureMetric")
        ):
            metric = getattr(self._amdsmi.AmdSmiTemperatureMetric, "CURRENT", None)
            if metric is not None:
                for temp_type in temp_types:
                    sensor = getattr(self._amdsmi.AmdSmiTemperatureType, temp_type, None)
                    if sensor is not None:
                        try:
                            temp = normalize_temperature_c(
                                self._amdsmi.amdsmi_get_temp_metric(handle, sensor, metric),
                                unit="millicelsius",
                            )
                            if temp is not None:
                                return temp
                        except Exception:
                            continue

        # Fallback to legacy API
        if hasattr(self._amdsmi, "amdsmi_get_gpu_temperature"):
            try:
                data = self._amdsmi.amdsmi_get_gpu_temperature(handle)
                if isinstance(data, dict):
                    return normalize_temperature_c(data.get("temperature"))
            except Exception:
                pass

        return None

    def _read_power(self, handle: Any) -> float | None:
        assert self._amdsmi is not None

        if hasattr(self._amdsmi, "amdsmi_get_power_info"):
            try:
                data = self._amdsmi.amdsmi_get_power_info(handle)
                if isinstance(data, dict):
                    raw = data.get("current_socket_power")
                    if raw is None:
                        raw = data.get("average_socket_power")
                    return normalize_power_w(raw, unit="auto")
            except Exception:
                pass

        if hasattr(self._amdsmi, "amdsmi_get_gpu_power"):
            try:
                data = self._amdsmi.amdsmi_get_gpu_power(handle)
                if isinstance(data, dict):
                    return normalize_power_w(data.get("avg_power"), unit="auto")
            except Exception:
                pass

        return None

    def _read_clocks(self, handle: Any) -> tuple[float | None, float | None]:
        assert self._amdsmi is not None

        core_clock = None
        memory_clock = None

        if hasattr(self._amdsmi, "amdsmi_get_clock_info") and hasattr(self._amdsmi, "AmdSmiClkType"):
            clk_type = self._amdsmi.AmdSmiClkType
            core_type = getattr(clk_type, "SYS", None)
            mem_type = getattr(clk_type, "MEM", None)

            if core_type is not None:
                try:
                    data = self._amdsmi.amdsmi_get_clock_info(handle, core_type)
                    if isinstance(data, dict):
                        core_clock = normalize_clock_mhz(data.get("clk") or data.get("sclk_freq"))
                except Exception:
                    pass

            if mem_type is not None:
                try:
                    data = self._amdsmi.amdsmi_get_clock_info(handle, mem_type)
                    if isinstance(data, dict):
                        memory_clock = normalize_clock_mhz(data.get("clk") or data.get("mclk_freq"))
                except Exception:
                    pass

        if memory_clock is None and hasattr(self._amdsmi, "amdsmi_get_gpu_clock_info"):
            try:
                data = self._amdsmi.amdsmi_get_gpu_clock_info(handle)
                if isinstance(data, dict):
                    core_clock = core_clock or normalize_clock_mhz(data.get("sclk_freq"))
                    memory_clock = normalize_clock_mhz(data.get("mclk_freq"))
            except Exception:
                pass

        return core_clock, memory_clock

    def _empty_metrics(self, index: int) -> GPUMetrics:
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

    def metrics(self, device: Any, index: int) -> GPUMetrics:
        if not self._ensure_initialized():
            return self._empty_metrics(index=index)

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

        assert self._amdsmi is not None

        if hasattr(self._amdsmi, "amdsmi_get_gpu_activity"):
            try:
                activity = self._amdsmi.amdsmi_get_gpu_activity(handle)
                if isinstance(activity, dict):
                    utilization = normalize_percent(activity.get("gfx_activity"))
            except Exception:
                pass

        if utilization is None and hasattr(self._amdsmi, "amdsmi_get_gpu_utilization"):
            try:
                activity = self._amdsmi.amdsmi_get_gpu_utilization(handle)
                if isinstance(activity, dict):
                    utilization = normalize_percent(activity.get("gpu_util"))
            except Exception:
                pass

        vram_usage = self._vram_usage(handle)
        memory_used = normalize_bytes(vram_usage.get("vram_used"))
        memory_total = normalize_bytes(vram_usage.get("vram_total"))

        temperature = self._read_temperature(handle)
        power_w = self._read_power(handle)
        core_clock, memory_clock = self._read_clocks(handle)

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
                name="omnismi-amdsmi-sampler",
                daemon=True,
            )
            self._sampler_stop_event = stop_event
            self._sampler_thread = thread

        thread.start()

    def _sampler_loop(self, stop_event: threading.Event) -> None:
        while not stop_event.wait(self._sample_interval_s):
            self._collect_all_metrics_once()

    def _collect_all_metrics_once(self) -> None:
        if not self._initialized or self._amdsmi is None:
            return

        for vendor_index, handle in self.devices():
            try:
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
        if not self._initialized or self._amdsmi is None:
            return

        try:
            if hasattr(self._amdsmi, "amdsmi_shut_down"):
                self._amdsmi.amdsmi_shut_down()
            elif hasattr(self._amdsmi, "amdsmi_shutdown"):
                self._amdsmi.amdsmi_shutdown()
        except Exception:
            pass
        self._initialized = False
