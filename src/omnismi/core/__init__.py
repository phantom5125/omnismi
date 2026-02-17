"""Core module for omnismi."""

from omnismi.core.detector import detect_gpus, get_available_vendors
from omnismi.core.device import GPUDevice, get_gpu, list_gpus

__all__ = [
    "detect_gpus",
    "get_available_vendors",
    "GPUDevice",
    "get_gpu",
    "list_gpus",
]
