"""Core type definitions for omnismi."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GPUInfo:
    """Static information about a GPU."""

    id: int
    name: str
    vendor: str
    driver_version: Optional[str] = None
    memory_total: Optional[int] = None  # in bytes


@dataclass
class GPUMetrics:
    """Dynamic metrics from a GPU."""

    id: int
    memory_used: Optional[int] = None  # in bytes
    memory_free: Optional[int] = None  # in bytes
    utilization_gpu: Optional[float] = None  # percentage
    utilization_memory: Optional[float] = None  # percentage
    temperature: Optional[float] = None  # celsius
    power_usage: Optional[float] = None  # watts
    clock_speed: Optional[float] = None  # MHz
