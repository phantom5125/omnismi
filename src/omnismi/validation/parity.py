"""Compare Omnismi metrics against vendor library readings."""

from __future__ import annotations

import argparse
import time
from dataclasses import asdict
from typing import Any, Callable

import omnismi as omi
from omnismi.normalize import (
    normalize_bytes,
    normalize_clock_mhz,
    normalize_percent,
    normalize_power_w,
    normalize_temperature_c,
)

DEFAULT_TOLERANCES = {
    "utilization_percent": 3.0,
    "memory_used_bytes": 64 * 1024 * 1024,
    "temperature_c": 3.0,
    "power_w": 8.0,
    "core_clock_mhz": 150.0,
}


def _collect_omnismi_samples(vendor: str, samples: int, interval_s: float) -> list[list[dict[str, Any]]]:
    devices = [gpu for gpu in omi.gpus() if gpu.info().vendor == vendor]
    if not devices:
        return []

    payload: list[list[dict[str, Any]]] = []
    for i in range(samples):
        rows: list[dict[str, Any]] = []
        for device in devices:
            metrics = device.metrics()
            rows.append(asdict(metrics))
        payload.append(rows)
        if i < samples - 1:
            time.sleep(interval_s)
    return payload


def _collect_nvidia_direct_samples(samples: int, interval_s: float) -> list[list[dict[str, Any]]]:
    try:
        import pynvml as nvml  # type: ignore
    except Exception:
        return []

    output: list[list[dict[str, Any]]] = []

    try:
        nvml.nvmlInit()
    except Exception:
        return []

    try:
        count = nvml.nvmlDeviceGetCount()
        for sample_idx in range(samples):
            rows: list[dict[str, Any]] = []
            for local_index in range(count):
                handle = nvml.nvmlDeviceGetHandleByIndex(local_index)

                utilization = None
                memory_used = None
                temperature = None
                power_w = None
                core_clock = None

                try:
                    util = nvml.nvmlDeviceGetUtilizationRates(handle)
                    utilization = normalize_percent(util.gpu)
                except Exception:
                    pass

                try:
                    mem = nvml.nvmlDeviceGetMemoryInfo(handle)
                    memory_used = normalize_bytes(mem.used)
                except Exception:
                    pass

                try:
                    temperature = normalize_temperature_c(
                        nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
                    )
                except Exception:
                    pass

                try:
                    power_w = normalize_power_w(nvml.nvmlDeviceGetPowerUsage(handle), unit="mw")
                except Exception:
                    pass

                try:
                    core_clock = normalize_clock_mhz(
                        nvml.nvmlDeviceGetClockInfo(handle, nvml.NVML_CLOCK_SM)
                    )
                except Exception:
                    pass

                rows.append(
                    {
                        "utilization_percent": utilization,
                        "memory_used_bytes": memory_used,
                        "temperature_c": temperature,
                        "power_w": power_w,
                        "core_clock_mhz": core_clock,
                    }
                )
            output.append(rows)
            if sample_idx < samples - 1:
                time.sleep(interval_s)
    finally:
        try:
            nvml.nvmlShutdown()
        except Exception:
            pass

    return output


def _amd_handles(amdsmi: Any) -> list[Any]:
    if hasattr(amdsmi, "amdsmi_get_processor_handles"):
        return list(amdsmi.amdsmi_get_processor_handles())
    if hasattr(amdsmi, "amdsmi_get_gpu_handles"):
        return list(amdsmi.amdsmi_get_gpu_handles())
    return []


def _collect_amd_direct_samples(samples: int, interval_s: float) -> list[list[dict[str, Any]]]:
    try:
        import amdsmi  # type: ignore
    except Exception:
        return []

    try:
        amdsmi.amdsmi_init()
    except Exception:
        return []

    output: list[list[dict[str, Any]]] = []

    try:
        handles = _amd_handles(amdsmi)
        for sample_idx in range(samples):
            rows: list[dict[str, Any]] = []
            for handle in handles:
                utilization = None
                memory_used = None
                temperature = None
                power_w = None
                core_clock = None

                try:
                    activity = amdsmi.amdsmi_get_gpu_activity(handle)
                    if isinstance(activity, dict):
                        utilization = normalize_percent(activity.get("gfx_activity"))
                except Exception:
                    pass

                try:
                    usage = amdsmi.amdsmi_get_gpu_vram_usage(handle)
                    if isinstance(usage, dict):
                        memory_used = normalize_bytes(usage.get("vram_used"))
                except Exception:
                    pass

                try:
                    sensor = amdsmi.AmdSmiTemperatureType.EDGE
                    metric = amdsmi.AmdSmiTemperatureMetric.CURRENT
                    temperature = normalize_temperature_c(
                        amdsmi.amdsmi_get_temp_metric(handle, sensor, metric),
                        unit="millicelsius",
                    )
                except Exception:
                    pass

                try:
                    power = amdsmi.amdsmi_get_power_info(handle)
                    if isinstance(power, dict):
                        raw_power = power.get("current_socket_power")
                        if raw_power is None:
                            raw_power = power.get("average_socket_power")
                        power_w = normalize_power_w(raw_power, unit="auto")
                except Exception:
                    pass

                try:
                    core_data = amdsmi.amdsmi_get_clock_info(handle, amdsmi.AmdSmiClkType.SYS)
                    if isinstance(core_data, dict):
                        core_clock = normalize_clock_mhz(core_data.get("clk"))
                except Exception:
                    pass

                rows.append(
                    {
                        "utilization_percent": utilization,
                        "memory_used_bytes": memory_used,
                        "temperature_c": temperature,
                        "power_w": power_w,
                        "core_clock_mhz": core_clock,
                    }
                )
            output.append(rows)
            if sample_idx < samples - 1:
                time.sleep(interval_s)
    finally:
        try:
            if hasattr(amdsmi, "amdsmi_shut_down"):
                amdsmi.amdsmi_shut_down()
            elif hasattr(amdsmi, "amdsmi_shutdown"):
                amdsmi.amdsmi_shutdown()
        except Exception:
            pass

    return output


def _flatten_pairs(
    ours: list[list[dict[str, Any]]],
    direct: list[list[dict[str, Any]]],
    metric_name: str,
) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []

    sample_count = min(len(ours), len(direct))
    for sample_index in range(sample_count):
        ours_rows = ours[sample_index]
        direct_rows = direct[sample_index]
        row_count = min(len(ours_rows), len(direct_rows))

        for row_index in range(row_count):
            left = ours_rows[row_index].get(metric_name)
            right = direct_rows[row_index].get(metric_name)
            if left is None or right is None:
                continue
            try:
                pairs.append((float(left), float(right)))
            except Exception:
                continue

    return pairs


def _evaluate_metric(
    ours: list[list[dict[str, Any]]],
    direct: list[list[dict[str, Any]]],
    metric_name: str,
    tolerance: float,
) -> tuple[str, float | None, int]:
    pairs = _flatten_pairs(ours, direct, metric_name)
    if not pairs:
        return "SKIP", None, 0

    max_diff = max(abs(left - right) for left, right in pairs)
    if max_diff <= tolerance:
        return "PASS", max_diff, len(pairs)
    return "FAIL", max_diff, len(pairs)


def run_parity(vendor: str, samples: int, interval_s: float) -> int:
    ours = _collect_omnismi_samples(vendor=vendor, samples=samples, interval_s=interval_s)
    if not ours:
        print(f"No Omnismi-visible {vendor} GPUs found.")
        return 0

    collector: Callable[[int, float], list[list[dict[str, Any]]]]
    if vendor == "nvidia":
        collector = _collect_nvidia_direct_samples
    else:
        collector = _collect_amd_direct_samples

    direct = collector(samples, interval_s)
    if not direct:
        print(f"Vendor direct readings unavailable for {vendor}.")
        return 0

    print(f"Parity check vendor={vendor} samples={samples}")
    print("metric,status,max_diff,tolerance,points")

    failed = False
    for metric_name, tolerance in DEFAULT_TOLERANCES.items():
        status, max_diff, points = _evaluate_metric(
            ours=ours,
            direct=direct,
            metric_name=metric_name,
            tolerance=tolerance,
        )

        if status == "FAIL":
            failed = True

        diff_display = "N/A" if max_diff is None else f"{max_diff:.4f}"
        print(f"{metric_name},{status},{diff_display},{tolerance},{points}")

    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m omnismi.validation.parity",
        description="Compare Omnismi metrics against vendor library readings.",
    )
    parser.add_argument("--vendor", choices=["nvidia", "amd"], required=True)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--interval", type=float, default=0.3)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.samples <= 0:
        parser.error("--samples must be > 0")

    return run_parity(vendor=args.vendor, samples=args.samples, interval_s=args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
