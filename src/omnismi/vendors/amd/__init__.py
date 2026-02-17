"""AMD GPU support via amdsmi."""

from typing import List, Optional

from omnismi.imports import get_amdsmi, is_amdsmi_available
from omnismi.types import GPUInfo, GPUMetrics
from omnismi.vendors.base import BaseVendor


# ROCm version compatibility mapping
# amdsmi API changed significantly between ROCm versions
ROCM_API_VERSION = {
    # ROCm 5.x - amdsmi init interface
    "5.x": {
        "init": "amdsmi_init",
        "get_gpu_handles": "amdsmi_get_gpu_handles",
        "get_gpu_name": "amdsmi_get_gpu_name",
    },
    # ROCm 6.x - similar to 5.x with some additions
    "6.x": {
        "init": "amdsmi_init",
        "get_gpu_handles": "amdsmi_get_gpu_handles",
        "get_gpu_name": "amdsmi_get_gpu_name",
    },
}


class AMDVendor(BaseVendor):
    """AMD GPU vendor implementation."""

    name = "amd"

    def __init__(self):
        self._initialized = False
        self._amdsmi = None

    def _ensure_init(self) -> bool:
        """Initialize amdsmi if not already done."""
        if not is_amdsmi_available():
            return False
        if self._initialized:
            return True

        try:
            self._amdsmi = get_amdsmi()
            self._amdsmi.amdsmi_init()
            self._initialized = True
            return True
        except Exception:
            return False

    def is_available(self) -> bool:
        """Check if AMD GPUs are available."""
        if not self._ensure_init():
            return False
        try:
            gpus = self._amdsmi.amdsmi_get_gpu_handles()
            return len(gpus) > 0
        except Exception:
            return False

    def list_gpus(self) -> List[GPUInfo]:
        """List all AMD GPUs."""
        if not self._ensure_init():
            return []
        try:
            gpus = self._amdsmi.amdsmi_get_gpu_handles()
            result = []
            for i, handle in enumerate(gpus):
                try:
                    name = self._amdsmi.amdsmi_get_gpu_name(handle)
                    if isinstance(name, bytes):
                        name = name.decode("utf-8")
                except Exception:
                    name = f"AMD GPU {i}"

                try:
                    vbios_info = self._amdsmi.amdsmi_get_gpu_vbios_info(handle)
                    driver_version = vbios_info.get("vbios_version", None)
                except Exception:
                    driver_version = None

                try:
                    mem_info = self._amdsmi.amdsmi_get_gpu_memory_info(handle)
                    memory_total = mem_info["vram_total"]
                except Exception:
                    memory_total = None

                result.append(
                    GPUInfo(
                        id=i,
                        name=name,
                        vendor=self.name,
                        driver_version=driver_version,
                        memory_total=memory_total,
                    )
                )
            return result
        except Exception:
            return []

    def get_info(self, gpu_id: int) -> Optional[GPUInfo]:
        """Get information for a specific AMD GPU."""
        gpus = self.list_gpus()
        for gpu in gpus:
            if gpu.id == gpu_id:
                return gpu
        return None

    def get_metrics(self, gpu_id: int) -> Optional[GPUMetrics]:
        """Get current metrics for a specific AMD GPU."""
        if not self._ensure_init():
            return None
        try:
            gpus = self._amdsmi.amdsmi_get_gpu_handles()
            if gpu_id >= len(gpus):
                return None

            handle = gpus[gpu_id]

            # Memory
            memory_used = None
            memory_free = None
            try:
                mem_info = self._amdsmi.amdsmi_get_gpu_memory_info(handle)
                memory_used = mem_info["vram_used"]
                memory_free = mem_info["vram_total"] - mem_info["vram_used"]
            except Exception:
                pass

            # Utilization
            utilization_gpu = None
            utilization_memory = None
            try:
                util = self._amdsmi.amdsmi_get_gpu_utilization(handle)
                utilization_gpu = util["gpu_util"]
                utilization_memory = util["memory_util"]
            except Exception:
                pass

            # Temperature
            temperature = None
            try:
                temp = self._amdsmi.amdsmi_get_gpu_temperature(handle)
                temperature = temp["temperature"]
            except Exception:
                pass

            # Power
            power_usage = None
            try:
                power = self._amdsmi.amdsmi_get_gpu_power(handle)
                power_usage = power["avg_power"]
            except Exception:
                pass

            # Clock speed
            clock_speed = None
            try:
                clock_info = self._amdsmi.amdsmi_get_gpu_clock_info(handle)
                clock_speed = clock_info["sclk_freq"]
            except Exception:
                pass

            return GPUMetrics(
                id=gpu_id,
                memory_used=memory_used,
                memory_free=memory_free,
                utilization_gpu=utilization_gpu,
                utilization_memory=utilization_memory,
                temperature=temperature,
                power_usage=power_usage,
                clock_speed=clock_speed,
            )
        except Exception:
            return None
