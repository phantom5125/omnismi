"""Omnismi: unified, minimal accelerator observability API."""

from omnismi.api import GPU, count, gpu, gpus
from omnismi.errors import BackendError, OmnismiError, ValidationError
from omnismi.models import GPUMetrics, GPUInfo

__version__ = "1.0.0"

__all__ = [
    "BackendError",
    "GPU",
    "GPUInfo",
    "GPUMetrics",
    "OmnismiError",
    "ValidationError",
    "count",
    "gpu",
    "gpus",
]
