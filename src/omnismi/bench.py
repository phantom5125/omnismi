"""Portable benchmark helpers for Omnismi CLI workflows."""

from __future__ import annotations

import statistics
import time
from typing import Any

_TORCH_DTYPES = {
    "fp32": "float32",
    "fp16": "float16",
    "bf16": "bfloat16",
}
_SUPPORTED_TORCH_VENDORS = {"nvidia", "amd"}


def execute_bandwidth_probe(
    *,
    device_index: int,
    device_vendor: str,
    pattern: str,
    dtype: str,
    buffer_bytes: int,
    minimum_iterations: int,
    warmup_seconds: float,
    duration_seconds: float,
    repeats: int,
    runtime: str,
    include_samples: bool,
) -> dict[str, Any]:
    started_at = _iso_timestamp()

    if runtime not in {"auto", "torch"}:
        return _skipped_result(
            started_at=started_at,
            message=f"Unsupported benchmark runtime `{runtime}`.",
        )

    if device_vendor not in _SUPPORTED_TORCH_VENDORS:
        return _skipped_result(
            started_at=started_at,
            message=f"Runtime `torch` currently supports NVIDIA and AMD devices only, not `{device_vendor}`.",
        )

    torch = _try_import_torch()
    if torch is None:
        return _skipped_result(
            started_at=started_at,
            message="PyTorch is not installed, so the portable torch runtime is unavailable.",
        )

    if not hasattr(torch, "cuda") or not bool(torch.cuda.is_available()):
        return _skipped_result(
            started_at=started_at,
            message="PyTorch did not report a CUDA/ROCm-capable runtime for the selected device.",
        )

    torch_dtype_name = _TORCH_DTYPES.get(dtype)
    if torch_dtype_name is None:
        return _skipped_result(
            started_at=started_at,
            message=f"Unsupported dtype `{dtype}` for the torch runtime.",
        )

    try:
        torch_dtype = getattr(torch, torch_dtype_name)
    except AttributeError:
        return _skipped_result(
            started_at=started_at,
            message=f"PyTorch runtime does not expose dtype `{torch_dtype_name}`.",
        )

    resolved_device = f"cuda:{device_index}"
    minimum_iterations = max(1, int(minimum_iterations))
    repeats = max(1, int(repeats))
    duration_seconds = max(0.0, float(duration_seconds))
    warmup_seconds = max(0.0, float(warmup_seconds))

    try:
        bytes_per_item = int(torch.empty((), dtype=torch_dtype).element_size())
        element_count = max(1, int(buffer_bytes) // max(1, bytes_per_item))
        resolved_buffer_bytes = element_count * bytes_per_item

        src_a = torch.empty(element_count, dtype=torch_dtype, device=resolved_device)
        src_b = torch.empty_like(src_a)
        dst = torch.empty_like(src_a)

        bytes_per_iteration = resolved_buffer_bytes * (2 if pattern == "copy" else 3)

        if warmup_seconds > 0.0:
            _run_warmup(
                torch=torch,
                device=resolved_device,
                pattern=pattern,
                src_a=src_a,
                src_b=src_b,
                dst=dst,
                minimum_iterations=minimum_iterations,
                warmup_seconds=warmup_seconds,
            )

        samples: list[dict[str, float | int]] = []
        sample_bandwidths: list[float] = []
        sample_seconds: list[float] = []

        for _ in range(repeats):
            target_iterations = minimum_iterations
            elapsed_seconds = _measure_bandwidth_seconds(
                torch=torch,
                device=resolved_device,
                pattern=pattern,
                src_a=src_a,
                src_b=src_b,
                dst=dst,
                iterations=target_iterations,
            )

            if duration_seconds > 0.0 and elapsed_seconds < duration_seconds:
                scaled_iterations = max(
                    target_iterations + 1,
                    int(target_iterations * (duration_seconds / max(elapsed_seconds, 1e-9))),
                )
                target_iterations = scaled_iterations
                elapsed_seconds = _measure_bandwidth_seconds(
                    torch=torch,
                    device=resolved_device,
                    pattern=pattern,
                    src_a=src_a,
                    src_b=src_b,
                    dst=dst,
                    iterations=target_iterations,
                )

            bandwidth = bytes_per_iteration * target_iterations / max(elapsed_seconds, 1e-12)
            sample_seconds.append(elapsed_seconds)
            sample_bandwidths.append(bandwidth)
            samples.append(
                {
                    "iterations": target_iterations,
                    "seconds": elapsed_seconds,
                    "bandwidth_bytes_per_second": bandwidth,
                }
            )

        metrics: dict[str, Any] = {
            "buffer_bytes": resolved_buffer_bytes,
            "bytes_per_iteration": bytes_per_iteration,
            "bandwidth_bytes_per_second": statistics.fmean(sample_bandwidths),
            "peak_bandwidth_bytes_per_second": max(sample_bandwidths),
        }
        if include_samples:
            metrics["sample_bandwidth_bytes_per_second"] = sample_bandwidths

        return {
            "execution": {
                "status": "success",
                "started_at": started_at,
                "ended_at": _iso_timestamp(),
                "errors": [],
            },
            "parameters": {
                "runtime": "torch",
                "pattern": pattern,
                "dtype": dtype,
                "buffer_bytes": resolved_buffer_bytes,
                "minimum_iterations": minimum_iterations,
                "warmup_seconds": warmup_seconds,
                "duration_seconds": duration_seconds,
                "repeats": repeats,
            },
            "statistics": _build_statistics(sample_seconds=samples),
            "metrics": metrics,
            "samples": samples if include_samples else None,
        }
    except Exception as exc:
        return {
            "execution": {
                "status": "error",
                "started_at": started_at,
                "ended_at": _iso_timestamp(),
                "errors": [str(exc)],
            },
            "parameters": {
                "runtime": "torch",
                "pattern": pattern,
                "dtype": dtype,
                "buffer_bytes": int(buffer_bytes),
                "minimum_iterations": minimum_iterations,
                "warmup_seconds": warmup_seconds,
                "duration_seconds": duration_seconds,
                "repeats": repeats,
            },
            "statistics": _empty_statistics(),
            "metrics": {},
            "samples": [] if include_samples else None,
        }


def _run_warmup(
    *,
    torch: Any,
    device: str,
    pattern: str,
    src_a: Any,
    src_b: Any,
    dst: Any,
    minimum_iterations: int,
    warmup_seconds: float,
) -> None:
    iterations = max(1, minimum_iterations)
    elapsed = _measure_bandwidth_seconds(
        torch=torch,
        device=device,
        pattern=pattern,
        src_a=src_a,
        src_b=src_b,
        dst=dst,
        iterations=iterations,
    )

    while elapsed < warmup_seconds and iterations < 1_000_000:
        scale = max(2, int(warmup_seconds / max(elapsed, 1e-9)))
        iterations = min(1_000_000, iterations * scale)
        elapsed = _measure_bandwidth_seconds(
            torch=torch,
            device=device,
            pattern=pattern,
            src_a=src_a,
            src_b=src_b,
            dst=dst,
            iterations=iterations,
        )


def _measure_bandwidth_seconds(
    *,
    torch: Any,
    device: str,
    pattern: str,
    src_a: Any,
    src_b: Any,
    dst: Any,
    iterations: int,
) -> float:
    _synchronize(torch=torch, device=device)
    started = time.perf_counter()
    if pattern == "copy":
        for _ in range(iterations):
            dst.copy_(src_a)
    elif pattern == "triad":
        for _ in range(iterations):
            torch.add(src_a, src_b, alpha=1.0, out=dst)
    else:
        raise ValueError(f"Unsupported bandwidth pattern `{pattern}`.")
    _synchronize(torch=torch, device=device)
    return max(0.0, time.perf_counter() - started)


def _synchronize(*, torch: Any, device: str) -> None:
    if hasattr(torch, "cuda") and hasattr(torch.cuda, "synchronize"):
        torch.cuda.synchronize(device=device)


def _build_statistics(*, sample_seconds: list[dict[str, float | int]]) -> dict[str, float | int | None]:
    seconds = [float(sample["seconds"]) for sample in sample_seconds]
    return {
        "sample_count": len(seconds),
        "min_seconds": min(seconds) if seconds else None,
        "mean_seconds": statistics.fmean(seconds) if seconds else None,
        "median_seconds": statistics.median(seconds) if seconds else None,
        "p95_seconds": _percentile(seconds, 0.95),
        "max_seconds": max(seconds) if seconds else None,
        "stdev_seconds": statistics.stdev(seconds) if len(seconds) > 1 else 0.0 if seconds else None,
    }


def _empty_statistics() -> dict[str, float | int | None]:
    return {
        "sample_count": 0,
        "min_seconds": None,
        "mean_seconds": None,
        "median_seconds": None,
        "p95_seconds": None,
        "max_seconds": None,
        "stdev_seconds": None,
    }


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None

    ordered = sorted(values)
    position = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction))))
    return ordered[position]


def _skipped_result(*, started_at: str, message: str) -> dict[str, Any]:
    return {
        "execution": {
            "status": "skipped",
            "started_at": started_at,
            "ended_at": _iso_timestamp(),
            "errors": [message],
        },
        "parameters": {},
        "statistics": _empty_statistics(),
        "metrics": {},
        "samples": None,
    }


def _iso_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _try_import_torch() -> Any | None:
    try:
        import torch
    except Exception:
        return None
    return torch
