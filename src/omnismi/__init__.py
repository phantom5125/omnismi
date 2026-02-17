"""Unified GPU Monitoring and Observability Layer."""

from omnismi.core.detector import detect_gpus
from omnismi.core.device import GPUDevice
from omnismi.types import GPUInfo, GPUMetrics

__version__ = "0.1.0"

__all__ = [
    "detect_gpus",
    "GPUDevice",
    "GPUInfo",
    "GPUMetrics",
]
