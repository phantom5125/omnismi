"""Isolated torch worker. Never imported to discover or enumerate devices."""

from __future__ import annotations

import contextlib
import json
import math
import statistics
import sys
import time
import uuid
from typing import Any

from omnismi import __version__


def execute(config: dict[str, Any]) -> dict[str, Any]:
    import torch

    vendor = config["vendor"]
    if vendor == "cambricon":
        import torch_mlu  # noqa: F401

        runtime, device_kind = torch.mlu, "mlu"
    else:
        runtime, device_kind = torch.cuda, "cuda"
        hip = bool(getattr(torch.version, "hip", None))
        if (vendor == "amd") != hip:
            return {"status": "INCONCLUSIVE", "reason": "runtime_vendor_mismatch"}
        if vendor == "alibaba":
            return {
                "status": "INCONCLUSIVE",
                "reason": "SAIL_torch_runtime_identity_not_verified",
            }
    if not runtime.is_available() or config["device"] >= runtime.device_count():
        return {"status": "INCONCLUSIVE", "reason": "runtime_device_unavailable"}
    index = config["device"]
    runtime.set_device(index)
    target = f"{device_kind}:{index}"
    props = runtime.get_device_properties(index)
    budget = config["memory_mib"] * 1024**2
    # Three float32 tensors; no allocation or workload scales with free VRAM.
    compute = config["mode"] == "compute"
    size = min(2048, 2 ** (math.isqrt(budget // 12).bit_length() - 1))
    count = size * size if compute else budget // 12
    if compute:
        if hasattr(torch, "set_float32_matmul_precision"):
            torch.set_float32_matmul_precision("highest")
        if hasattr(torch, "backends") and hasattr(torch.backends, "cuda"):
            torch.backends.cuda.matmul.allow_tf32 = False
    a = torch.empty(
        (size, size) if compute else count, dtype=torch.float32, device=target
    )
    b, c = torch.empty_like(a), torch.empty_like(a)
    sync = lambda: runtime.synchronize(index)  # noqa: E731
    checks = []
    # Alternate exact bit-friendly values. Copy and triad must actually execute.
    for value in (0.0, 1.0, -1.0, 65536.0):
        a.fill_(value)
        b.fill_(value)
        c.copy_(a)
        sync()
        checks.append(
            {"name": "memory_copy", "pattern": value, "passed": bool(torch.equal(a, c))}
        )
        torch.add(a, b, out=c)
        a.fill_(value * 2)
        sync()
        checks.append(
            {"name": "vector_add", "pattern": value, "passed": bool(torch.equal(a, c))}
        )
    if not all(check["passed"] for check in checks):
        return {
            "status": "FAIL",
            "reason": "data_mismatch",
            "checks": checks,
            "affected_units": ["memory_or_compute_path"],
            "hardware_fault_confirmed": False,
        }
    identity = {
        "name": str(props.name),
        "uuid": str(getattr(props, "uuid", "")) or None,
        "runtime_device_index": index,
        "vendor": vendor,
        "runtime_version": str(torch.__version__),
    }
    if config["mode"] == "self-test":
        del a, b, c
        # A small exactly representable matrix multiplication tests a second path.
        size = 64
        left = torch.ones((size, size), dtype=torch.float32, device=target)
        right = torch.ones_like(left)
        result = torch.mm(left, right)
        expected = torch.full_like(left, float(size))
        sync()
        checks.append(
            {"name": "matrix_multiply", "passed": bool(torch.equal(result, expected))}
        )
        return {
            "status": "PASS" if checks[-1]["passed"] else "FAIL",
            "checks": checks,
            "identity": identity,
            "tested_buffer_bytes": count * 4,
            "hardware_fault_confirmed": False,
        }
    a.fill_(1)
    b.fill_(2)

    def operation():
        if compute:
            torch.mm(a, b, out=c)
        elif config["pattern"] == "copy":
            c.copy_(a)
        else:
            torch.add(a, b, out=c)

    for _ in range(5):
        operation()
    sync()
    samples = []
    byte_count = count * 4 * (2 if config["pattern"] == "copy" else 3)
    work = 2 * size**3 if compute else byte_count
    for _ in range(config["repeats"]):
        sync()
        start = time.perf_counter()
        for _ in range(20):
            operation()
        sync()
        elapsed = time.perf_counter() - start
        if elapsed <= 0:
            raise ValueError("Nonpositive measurement interval")
        samples.append(
            {
                "seconds": elapsed,
                "iterations": 20,
                ("flops_per_iteration" if compute else "bytes_per_iteration"): work,
                "value": work * 20 / elapsed,
            }
        )
    if compute:
        b.fill_(2 * size)
        if not torch.equal(c, b):
            return {
                "status": "FAIL",
                "reason": "matmul_data_mismatch",
                "checks": checks,
                "hardware_fault_confirmed": False,
            }
    values = [sample["value"] for sample in samples]
    signature = {
        "vendor": vendor,
        "sku": identity["name"],
        "probe": "compute" if compute else "bandwidth",
        "probe_version": f"omnismi/{__version__}/torch-bounded-v2"
        + ("/matmul-fp32-highest" if compute else ""),
        "pattern": "matmul" if compute else config["pattern"],
        "dtype": "fp32",
        "buffer_bytes": count * 4,
        "byte_convention": "dense_2mnk" if compute else "read_plus_write",
        "runtime": f"torch-{device_kind}",
        "runtime_version": str(torch.__version__),
        "device_count": 1,
    }
    return {
        "status": "PASS",
        "identity": identity,
        "checks": checks,
        "samples": samples,
        "standard_deviation": statistics.stdev(values),
        "coefficient_of_variation": statistics.stdev(values) / statistics.fmean(values),
        "measurement": {
            "schema_version": 1,
            "metric": "compute_throughput" if compute else "memory_bandwidth",
            "unit": "FLOP/s" if compute else "bytes/s",
            "value": statistics.fmean(values),
            "signature": signature,
            "source": {
                "id": str(uuid.uuid4()),
                "description": "Synchronized torch probe with retained samples.",
            },
        },
    }


def main() -> None:
    try:
        with contextlib.redirect_stdout(sys.stderr):
            result = execute(json.loads(sys.argv[1]))
    except Exception as exc:
        result = {
            "status": "INCONCLUSIVE",
            "reason": "runtime_error",
            "detail": str(exc),
        }
    print(json.dumps(result, allow_nan=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
