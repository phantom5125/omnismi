"""AMD backend powered by amdsmi."""

from __future__ import annotations

import time
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

    def __init__(self) -> None:
        self._amdsmi: Any | None = None
        self._import_failed = False
        self._initialized = False

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
        assert self._amdsmi is not None

        if (
            hasattr(self._amdsmi, "amdsmi_get_temp_metric")
            and hasattr(self._amdsmi, "AmdSmiTemperatureType")
            and hasattr(self._amdsmi, "AmdSmiTemperatureMetric")
        ):
            sensor = getattr(self._amdsmi.AmdSmiTemperatureType, "EDGE", None)
            metric = getattr(self._amdsmi.AmdSmiTemperatureMetric, "CURRENT", None)
            if sensor is not None and metric is not None:
                try:
                    return normalize_temperature_c(
                        self._amdsmi.amdsmi_get_temp_metric(handle, sensor, metric),
                        unit="millicelsius",
                    )
                except Exception:
                    pass

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

    def metrics(self, device: Any, index: int) -> GPUMetrics:
        _, handle = device
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
            index=index,
            utilization_percent=utilization,
            memory_used_bytes=memory_used,
            memory_total_bytes=memory_total,
            temperature_c=temperature,
            power_w=power_w,
            core_clock_mhz=core_clock,
            memory_clock_mhz=memory_clock,
            timestamp_ns=timestamp_ns,
        )

    def close(self) -> None:
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
