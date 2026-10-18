"""Validate and normalize the native HGGC worker's bounded JSON protocol."""

from __future__ import annotations

import json
import math
import os
import shutil
import statistics
import uuid
from typing import Any

from omnismi import __version__
from omnismi.backends.command import query_text

PROBE_VERSION = "hggc-tiled16-v1"


def execute(config: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    executable = os.environ.get("OMNISMI_SAIL_PROBE") or shutil.which(
        "omnismi-sail-probe"
    )
    if not executable:
        return {
            "status": "INCONCLUSIVE",
            "reason": "SAIL_native_probe_not_installed",
            "detail": "Run omnismi sail-build with the installed SAIL SDK "
            "and set OMNISMI_SAIL_PROBE.",
        }
    command = [
        executable,
        "--run",
        config["mode"],
        str(config["device"]),
        str(config["memory_mib"]),
        str(config["repeats"]),
        config["pattern"],
    ]
    return normalize(json.loads(query_text(command, timeout=timeout)), config)


def normalize(payload: Any, config: dict[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(payload, dict)
        or type(payload.get("schema_version")) is not int
        or payload["schema_version"] != 1
        or payload.get("collector") != "omnismi-sail-probe"
        or payload.get("probe_version") != PROBE_VERSION
        or not isinstance(payload.get("status"), str)
        or payload["status"] not in {"PASS", "FAIL", "INCONCLUSIVE"}
    ):
        raise ValueError("Invalid SAIL probe protocol/version")
    if payload["status"] == "INCONCLUSIVE":
        return {
            "status": "INCONCLUSIVE",
            "reason": "SAIL_runtime_error",
            "detail": str(payload.get("detail", "Runtime did not complete"))[:4096],
        }
    identity = payload.get("identity")
    if (
        not isinstance(identity, dict)
        or identity.get("vendor") != "alibaba"
        or type(identity.get("runtime_device_index")) is not int
        or identity["runtime_device_index"] != config["device"]
        or not isinstance(identity.get("name"), str)
        or not identity["name"].strip()
        or len(identity["name"]) > 256
        or any(
            type(identity.get(key)) is not int or identity[key] <= 0
            for key in ("runtime_version", "driver_version")
        )
    ):
        raise ValueError("Invalid SAIL runtime identity")
    budget = config["memory_mib"] * 1024**2
    compute = config["mode"] == "compute"
    dimension = (
        min(2048, 2 ** (math.isqrt(budget // 12).bit_length() - 1)) if compute else 64
    )
    count = dimension**2 if compute else budget // 12
    if (
        payload.get("mode") != config["mode"]
        or payload.get("pattern") != config["pattern"]
        or type(payload.get("buffer_bytes")) is not int
        or payload["buffer_bytes"] != count * 4
        or type(payload.get("matrix_dimension")) is not int
        or payload["matrix_dimension"] != dimension
        or type(payload.get("iterations")) is not int
        or payload["iterations"] != 20
    ):
        raise ValueError("SAIL probe configuration mismatch")
    checks = payload.get("checks")
    names = ["memory_copy", "vector_add"] * 4
    last = "matrix_multiply" if config["mode"] == "self-test" else "timed_result"
    if (
        not isinstance(checks, list)
        or len(checks) not in {8, 9}
        or any(
            not isinstance(item, dict) or type(item.get("passed")) is not bool
            for item in checks
        )
        or [item.get("name") for item in checks]
        != names + ([last] if len(checks) == 9 else [])
    ):
        raise ValueError("Invalid SAIL correctness evidence")
    passed = all(item["passed"] for item in checks)
    if (payload["status"] == "PASS" and (not passed or len(checks) != 9)) or (
        payload["status"] == "FAIL" and passed
    ):
        raise ValueError("SAIL status contradicts correctness evidence")
    result = {
        "status": payload["status"],
        "identity": identity,
        "checks": checks,
        "tested_buffer_bytes": count * 4,
        "hardware_fault_confirmed": False,
    }
    if not passed:
        return {
            **result,
            "reason": "data_mismatch",
            "affected_units": ["memory_or_compute_path"],
        }
    if config["mode"] == "self-test":
        return result
    seconds = payload.get("seconds")
    if (
        not isinstance(seconds, list)
        or len(seconds) != config["repeats"]
        or any(
            type(value) not in (int, float) or not math.isfinite(value) or value <= 0
            for value in seconds
        )
    ):
        raise ValueError("Invalid SAIL timing samples")
    work = (
        2 * dimension**3
        if compute
        else count * 4 * (2 if config["pattern"] == "copy" else 3)
    )
    samples = [
        {
            "seconds": value,
            "iterations": 20,
            "flops_per_iteration" if compute else "bytes_per_iteration": work,
            "value": work * 20 / value,
        }
        for value in seconds
    ]
    values = [sample["value"] for sample in samples]
    if not all(math.isfinite(value) and value > 0 for value in values):
        raise ValueError("Invalid SAIL throughput")
    mean, deviation = statistics.fmean(values), statistics.stdev(values)
    signature = {
        "vendor": "alibaba",
        "sku": identity["name"],
        "probe": "compute" if compute else "bandwidth",
        "probe_version": f"omnismi/{__version__}/{PROBE_VERSION}",
        "pattern": "matmul" if compute else config["pattern"],
        "dtype": "fp32",
        "buffer_bytes": count * 4,
        "byte_convention": "dense_2mnk" if compute else "read_plus_write",
        "runtime": "sail-hggc",
        "runtime_version": str(identity["runtime_version"]),
        "driver_version": str(identity["driver_version"]),
        "device_count": 1,
    }
    return {
        **result,
        "samples": samples,
        "standard_deviation": deviation,
        "coefficient_of_variation": deviation / mean,
        "measurement": {
            "schema_version": 1,
            "metric": "compute_throughput" if compute else "memory_bandwidth",
            "unit": "FLOP/s" if compute else "bytes/s",
            "value": mean,
            "signature": signature,
            "source": {
                "id": str(uuid.uuid4()),
                "description": "Synchronized native SAIL HGGC probe "
                "with retained samples.",
            },
        },
    }
