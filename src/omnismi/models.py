"""Public data models for Omnismi."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

VendorName = Literal["nvidia", "amd", "google", "alibaba", "cambricon"]


# Python 3.9 supports frozen records, but automatic slots require Python 3.10.
@dataclass(frozen=True, **({"slots": True} if sys.version_info >= (3, 10) else {}))
class GPUInfo:
    """Static GPU information exposed by the public API."""

    index: int
    vendor: VendorName
    name: str
    uuid: str | None
    driver: str | None
    memory_total_bytes: int | None


@dataclass(frozen=True, **({"slots": True} if sys.version_info >= (3, 10) else {}))
class GPUMetrics:
    """Dynamic GPU metrics exposed by the public API."""

    index: int
    utilization_percent: float | None
    memory_used_bytes: int | None
    memory_total_bytes: int | None
    temperature_c: float | None
    power_w: float | None
    core_clock_mhz: float | None
    memory_clock_mhz: float | None
    timestamp_ns: int
