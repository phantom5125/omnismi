"""Explicit accelerator workloads in a bounded, disposable subprocess."""

from __future__ import annotations

import json
import math
import sys
import time
from typing import Any

from omnismi import __version__
from omnismi.backends.command import query_text
from omnismi.errors import BackendError


def _validate(
    *,
    mode: str,
    vendor: str,
    device: int = 0,
    memory_mib: int = 64,
    repeats: int = 5,
    timeout: float = 30.0,
    pattern: str = "copy",
) -> None:
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
    _validate(
        mode=mode,
        vendor=vendor,
        device=device,
        memory_mib=memory_mib,
        repeats=repeats,
        timeout=timeout,
        pattern=pattern,
    )
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
        if vendor == "alibaba":
            from omnismi.sail_runtime import execute

            payload = execute(config, timeout=timeout)
        else:
            payload = json.loads(
                query_text(
                    [sys.executable, "-m", "omnismi.probe_worker", json.dumps(config)],
                    timeout=timeout,
                )
            )
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("status"), str)
            or payload["status"] not in {"PASS", "FAIL", "INCONCLUSIVE"}
        ):
            raise ValueError("Invalid probe worker response")
        report["status"], report["data"] = payload["status"], payload
    except (OSError, ValueError, BackendError) as exc:
        report["data"] = {
            "reason": "worker_unavailable_or_incomplete",
            "detail": str(exc),
        }
    return report


def run_suite(
    *,
    vendor: str,
    device: int = 0,
    memory_mib: int = 64,
    repeats: int = 5,
    timeout: float = 90.0,
) -> dict[str, Any]:
    """Run correctness, copy, triad and compute sequentially under one deadline."""
    _validate(
        mode="self-test",
        vendor=vendor,
        device=device,
        memory_mib=memory_mib,
        repeats=repeats,
        timeout=timeout,
    )
    deadline = time.monotonic() + timeout
    results, skipped = [], []
    stop_reason = None
    for mode, pattern in (
        ("self-test", "copy"),
        ("bandwidth", "copy"),
        ("bandwidth", "triad"),
        ("compute", "copy"),
    ):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            stop_reason = "suite_deadline_exhausted"
        if stop_reason:
            skipped.append({"mode": mode, "pattern": pattern, "reason": stop_reason})
            continue
        report = run_probe(
            mode=mode,
            vendor=vendor,
            device=device,
            memory_mib=memory_mib,
            repeats=repeats,
            timeout=remaining,
            pattern=pattern,
        )
        results.append({"mode": mode, "pattern": pattern, "report": report})
        if report["status"] != "PASS":
            stop_reason = "prior_probe_did_not_pass"
    statuses = {item["report"]["status"] for item in results}
    status = (
        "FAIL"
        if "FAIL" in statuses
        else ("INCONCLUSIVE" if skipped or "INCONCLUSIVE" in statuses else "PASS")
    )
    return {
        "schema_version": 1,
        "report_type": "active_probe_suite",
        "tool_version": __version__,
        "status": status,
        "scope": {
            "explicit_execution": True,
            "vendor": vendor,
            "runtime_device_index": device,
            "timeout_seconds": timeout,
            "tensor_budget_bytes": memory_mib * 1024**2,
            "current_hardware_health": "INCONCLUSIVE",
            "performance_expectation": "not_evaluated",
        },
        "data": {"results": results, "skipped": skipped},
        "evidence": [],
        "sources": [],
        "limitations": [
            "PASS covers executed checks, not whole-device health "
            "or expected performance.",
            "Use perf-doctor with recorded conditions and a baseline "
            "to assess performance.",
            "Separate runtime sessions retain identity per probe; "
            "the suite is not an atomic hardware snapshot.",
            "Tensor budget excludes runtime context and allocator overhead.",
        ],
    }
