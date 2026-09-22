"""Explicit accelerator workloads in a bounded, disposable subprocess."""

from __future__ import annotations

import json
import math
import sys
from typing import Any

from omnismi import __version__
from omnismi.backends.command import query_text
from omnismi.errors import BackendError


def run_probe(
    *,
    mode: str,
    vendor: str,
    device: int = 0,
    memory_mib: int = 64,
    repeats: int = 5,
    timeout: float = 30.0,
    pattern: str = "copy",
) -> dict[str, Any]:
    """Execute only on explicit request. Device indexes are runtime-local."""
    if mode not in {"bandwidth", "compute", "self-test"} or vendor not in {
        "nvidia",
        "amd",
        "alibaba",
        "cambricon",
    }:
        raise ValueError("Unsupported probe mode/vendor")
    if type(device) is not int or not 0 <= device <= 4095:
        raise ValueError("Device must be a runtime index in 0..4095")
    if type(memory_mib) is not int or not 1 <= memory_mib <= 4096:
        raise ValueError("Memory budget must be 1..4096 MiB")
    if (
        type(repeats) is not int
        or not 2 <= repeats <= 100
        or pattern not in {"copy", "triad"}
    ):
        raise ValueError("Require 2..100 repeats and a copy/triad pattern")
    if not math.isfinite(timeout) or not 0 < timeout <= 600:
        raise ValueError("Timeout must be in (0, 600] seconds")
    config = dict(
        mode=mode,
        vendor=vendor,
        device=device,
        memory_mib=memory_mib,
        repeats=repeats,
        pattern=pattern,
    )
    report = {
        "schema_version": 1,
        "report_type": "active_probe",
        "tool_version": __version__,
        "status": "INCONCLUSIVE",
        "scope": {
            "explicit_execution": True,
            "runtime_device_index": device,
            "timeout_seconds": timeout,
            "tensor_budget_bytes": memory_mib * 1024**2,
            "current_hardware_health": "INCONCLUSIVE",
        },
        "data": {},
        "evidence": [],
        "sources": [],
        "limitations": [
            "Tests cover allocated buffers and selected operations only.",
            "Tensor budget excludes runtime context and allocator overhead.",
        ],
    }
    try:
        payload = json.loads(
            query_text(
                [sys.executable, "-m", "omnismi.probe_worker", json.dumps(config)],
                timeout=timeout,
            )
        )
        if not isinstance(payload, dict) or payload.get("status") not in {
            "PASS",
            "FAIL",
            "INCONCLUSIVE",
        }:
            raise ValueError("Invalid probe worker response")
        report["status"], report["data"] = payload["status"], payload
    except (OSError, ValueError, BackendError) as exc:
        report["data"] = {
            "reason": "worker_unavailable_or_incomplete",
            "detail": str(exc),
        }
    return report
