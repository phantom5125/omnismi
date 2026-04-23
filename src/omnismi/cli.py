"""Command-line interface for Omnismi."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import socket
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import omnismi as omi
from omnismi import __version__
from omnismi.backends import registered_backends
from omnismi.profiles import get_profile, list_profiles, profile_matches_device_name, profile_to_dict

_SUBCOMMANDS = {"doctor", "bench", "validate-spec"}
_BACKEND_NAMES = {
    "NvidiaBackend": "nvml",
    "AmdBackend": "amdsmi",
    "GoogleTpuBackend": "tpumonitoring",
}
_VISIBLE_STATUS_MATCHED = "MATCHED"
_VISIBLE_STATUS_MISMATCHED = "MISMATCHED"
_VISIBLE_STATUS_UNKNOWN = "UNKNOWN"
_PROFILE_MEMORY_TOLERANCE_BYTES = 1024**3
_VISIBILITY_CONTROL_ENV_VARS = (
    "CUDA_VISIBLE_DEVICES",
    "NVIDIA_VISIBLE_DEVICES",
    "HIP_VISIBLE_DEVICES",
    "ROCR_VISIBLE_DEVICES",
    "GPU_DEVICE_ORDINAL",
    "TPU_VISIBLE_DEVICES",
    "TPU_VISIBLE_CHIPS",
    "TPU_CHIPS_PER_PROCESS_BOUNDS",
)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_STYLE_RESET = "\x1b[0m"
_STYLE_CODES = {
    "bold": "\x1b[1m",
    "dim": "\x1b[2m",
    "cyan": "\x1b[36m",
    "blue": "\x1b[34m",
    "green": "\x1b[32m",
    "yellow": "\x1b[33m",
    "red": "\x1b[31m",
    "magenta": "\x1b[35m",
}
_NET_IO_SAMPLE: tuple[float, int, int] | None = None


def _build_common_scope_group(parser: argparse.ArgumentParser) -> None:
    scope_group = parser.add_mutually_exclusive_group()
    scope_group.add_argument(
        "--device",
        action="append",
        type=int,
        default=None,
        help="Restrict output to one or more global Omnismi device indexes.",
    )
    scope_group.add_argument(
        "--all-devices",
        action="store_true",
        help="Include every visible device.",
    )
    parser.add_argument(
        "--vendor",
        choices=["nvidia", "amd", "google"],
        help="Restrict output to one vendor.",
    )


def _add_color_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="Control ANSI color in human-readable output.",
    )
    parser.add_argument(
        "--no-color",
        action="store_const",
        const="never",
        dest="color",
        help="Alias for `--color never`.",
    )


def build_overview_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omnismi",
        description="Show a cross-vendor accelerator summary for the current runtime.",
    )
    _build_common_scope_group(parser)
    parser.add_argument(
        "--wide",
        action="store_true",
        help="Show additional device and runtime columns.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Refresh the human-readable table once per second until interrupted.",
    )
    parser.add_argument(
        "-o",
        "--output",
        choices=["table", "json", "yaml"],
        default="table",
        help="Choose a human-readable table or structured output format.",
    )
    _add_color_arguments(parser)
    return parser


def build_root_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omnismi",
        description="Omnismi command-line tools.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Explain discovery mismatches and partial visibility.",
    )
    _build_common_scope_group(doctor_parser)
    doctor_parser.add_argument(
        "-o",
        "--output",
        choices=["table", "json", "yaml"],
        default="table",
        help="Choose a human-readable table or structured output format.",
    )
    doctor_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show all backend details even when there are no findings.",
    )
    _add_color_arguments(doctor_parser)

    bench_parser = subparsers.add_parser(
        "bench",
        help="Portable accelerator benchmark probes.",
    )
    bench_parser.add_argument(
        "bench_command",
        nargs="?",
        help="Planned subcommand such as bandwidth, matmul, or suite.",
    )

    validate_parser = subparsers.add_parser(
        "validate-spec",
        help="Compare the current machine against an expected profile.",
    )
    _build_common_scope_group(validate_parser)
    validate_parser.add_argument(
        "--profile",
        required=True,
        help="Curated hardware profile name such as h100-pcie-80gb.",
    )
    validate_parser.add_argument(
        "-o",
        "--output",
        choices=["table", "json", "yaml"],
        default="table",
        help="Choose a human-readable table or structured output format.",
    )
    validate_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed per-device check results.",
    )
    _add_color_arguments(validate_parser)

    return parser


def _looks_like_container() -> bool:
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return True
    if Path("/.dockerenv").exists():
        return True
    cgroup_path = Path("/proc/1/cgroup")
    if cgroup_path.exists():
        try:
            text = cgroup_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        hints = ("docker", "containerd", "kubepods", "podman", "lxc")
        return any(hint in text for hint in hints)
    return False


def _detect_environment() -> dict[str, Any]:
    orchestrator = "kubernetes" if os.environ.get("KUBERNETES_SERVICE_HOST") else "none"
    execution_scope = "container" if _looks_like_container() else "host"
    visibility_controls = _collect_visibility_controls()
    visibility_scope = "runtime-scoped" if execution_scope == "container" or visibility_controls else "host-global"

    return {
        "platform": platform.system().lower(),
        "hostname": socket.gethostname(),
        "execution_scope": execution_scope,
        "orchestrator": orchestrator,
        "visibility_scope": visibility_scope,
        "visibility_controls": visibility_controls,
        "torch_visible_device_count": _torch_visible_device_count(),
    }


def _collect_visibility_controls() -> list[dict[str, str]]:
    controls: list[dict[str, str]] = []

    for name in _VISIBILITY_CONTROL_ENV_VARS:
        value = os.environ.get(name)
        if value is None:
            continue
        normalized = value.strip() or "<empty>"
        controls.append({"name": name, "value": normalized})

    return controls


def _resolve_primary_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            address = sock.getsockname()[0]
            if address:
                return address
    except OSError:
        pass

    try:
        address = socket.gethostbyname(socket.gethostname())
    except OSError:
        return None

    if address.startswith("127."):
        return None
    return address


def _try_import_psutil() -> Any | None:
    try:
        import psutil  # type: ignore
    except Exception:
        return None
    return psutil


def _torch_visible_device_count() -> int | None:
    try:
        import torch
    except Exception:
        return None

    try:
        return int(torch.cuda.device_count())
    except Exception:
        return None


def _backend_name(backend: Any) -> str:
    return _BACKEND_NAMES.get(type(backend).__name__, backend.vendor)


def _collect_backend_report() -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []

    for backend in registered_backends():
        status = "no_devices"
        reason = None

        try:
            available = bool(backend.available())
        except Exception as exc:
            available = False
            status = "error"
            reason = str(exc)
        else:
            if available:
                status = "ok"
            elif bool(getattr(backend, "_import_failed", False)):
                status = "missing_dependency"
                reason = f"{_backend_name(backend)} import failed"

        reports.append(
            {
                "vendor": backend.vendor,
                "backend": _backend_name(backend),
                "status": status,
                "reason": reason,
            }
        )

    return reports


def _collect_system_metrics(
    devices: list[dict[str, Any]],
    backends: list[dict[str, Any]],
) -> dict[str, Any]:
    global _NET_IO_SAMPLE

    metrics = {
        "ip_address": _resolve_primary_ip(),
        "uptime_seconds": None,
        "cpu_percent": None,
        "memory_used_bytes": None,
        "memory_total_bytes": None,
        "net_rx_bytes_per_s": None,
        "net_tx_bytes_per_s": None,
        "driver_label": _driver_label(devices=devices, backends=backends),
    }

    psutil = _try_import_psutil()
    if psutil is None:
        return metrics

    try:
        metrics["cpu_percent"] = float(psutil.cpu_percent(interval=None))
    except Exception:
        pass

    try:
        memory = psutil.virtual_memory()
        metrics["memory_used_bytes"] = int(memory.used)
        metrics["memory_total_bytes"] = int(memory.total)
    except Exception:
        pass

    try:
        metrics["uptime_seconds"] = max(0.0, time.time() - float(psutil.boot_time()))
    except Exception:
        pass

    try:
        counters = psutil.net_io_counters()
        now = time.time()
        rx_total = int(counters.bytes_recv)
        tx_total = int(counters.bytes_sent)
        if _NET_IO_SAMPLE is not None:
            previous_time, previous_rx, previous_tx = _NET_IO_SAMPLE
            elapsed = now - previous_time
            if elapsed > 0.0:
                metrics["net_rx_bytes_per_s"] = max(0.0, (rx_total - previous_rx) / elapsed)
                metrics["net_tx_bytes_per_s"] = max(0.0, (tx_total - previous_tx) / elapsed)
        _NET_IO_SAMPLE = (now, rx_total, tx_total)
    except Exception:
        pass

    return metrics


def _driver_label(devices: list[dict[str, Any]], backends: list[dict[str, Any]]) -> str:
    drivers = sorted({device["driver"] for device in devices if device["driver"]})
    if len(drivers) == 1:
        return drivers[0]
    if len(drivers) > 1:
        return "Mixed"
    if any(item["status"] == "ok" for item in backends):
        return "Visible"
    return "Unavailable"


def _device_state(info: dict[str, Any], metrics: dict[str, Any]) -> str:
    useful_metric_values = [
        metrics.get("utilization_percent"),
        metrics.get("memory_used_bytes"),
        metrics.get("memory_total_bytes"),
        metrics.get("temperature_c"),
        metrics.get("power_w"),
    ]

    if info.get("memory_total_bytes") is None and all(value is None for value in useful_metric_values):
        return "ERROR"
    if info.get("memory_total_bytes") is None or any(value is None for value in useful_metric_values):
        return "PARTIAL"
    return "OK"


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value / (1024**3):.1f}GB"


def _format_percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.0f}%"


def _format_temperature(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.0f}\N{DEGREE SIGN}C"


def _format_power(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.0f}W"


def _format_clock(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.0f}MHz"


def _format_memory_pair(used: int | None, total: int | None) -> str:
    if used is None and total is None:
        return "-"
    return f"{_format_bytes(used)} / {_format_bytes(total)}"


def _selected_device_indexes(args: argparse.Namespace) -> set[int] | None:
    if not args.device:
        return None
    return {index for index in args.device if index >= 0}


def _build_device_record(device: omi.GPU) -> dict[str, Any]:
    info = asdict(device.info())
    metrics = asdict(device.metrics())
    return {
        "index": info["index"],
        "vendor": info["vendor"],
        "name": info["name"],
        "uuid": info["uuid"],
        "driver": info["driver"],
        "memory_total_bytes": info["memory_total_bytes"],
        "metrics": metrics,
        "state": _device_state(info=info, metrics=metrics),
    }


def _filter_devices(devices: list[dict[str, Any]], args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    filtered = list(devices)

    if args.vendor is not None:
        filtered = [device for device in filtered if device["vendor"] == args.vendor]

    selected_indexes = _selected_device_indexes(args)
    if selected_indexes is not None:
        missing = sorted(index for index in selected_indexes if index not in {d["index"] for d in filtered})
        filtered = [device for device in filtered if device["index"] in selected_indexes]
        if missing:
            warnings.append(
                "Requested device indexes were not visible in the current runtime: "
                + ", ".join(str(index) for index in missing)
            )

    return filtered, warnings


def build_overview_report(args: argparse.Namespace, argv: list[str]) -> dict[str, Any]:
    environment = _detect_environment()
    backend_reports = _collect_backend_report()
    all_devices = [_build_device_record(device) for device in omi.gpus()]
    devices, warnings = _filter_devices(all_devices, args)
    system_metrics = _collect_system_metrics(devices=devices, backends=backend_reports)

    torch_count = environment["torch_visible_device_count"]
    if torch_count is None:
        visibility_status = _VISIBLE_STATUS_UNKNOWN
    elif torch_count == len(all_devices):
        visibility_status = _VISIBLE_STATUS_MATCHED
    else:
        visibility_status = _VISIBLE_STATUS_MISMATCHED
        warnings.append(
            f"PyTorch reports {torch_count} visible GPU(s), but Omnismi found {len(all_devices)}."
        )

    device_states = [device["state"] for device in devices]
    healthy_count = sum(state == "OK" for state in device_states)
    partial_count = sum(state == "PARTIAL" for state in device_states)
    error_count = sum(state == "ERROR" for state in device_states)

    overall_status = "EMPTY"
    if devices:
        overall_status = "OK"
        if error_count > 0:
            overall_status = "ERROR"
        elif partial_count > 0 or visibility_status == _VISIBLE_STATUS_MISMATCHED:
            overall_status = "PARTIAL"

    report = {
        "apiVersion": "omnismi/v1alpha1",
        "kind": "OverviewReport",
        "metadata": {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "omnismi_version": __version__,
        },
        "command": {
            "argv": ["omnismi", *argv],
            "output": args.output,
        },
        "environment": environment,
        "system": system_metrics,
        "backends": backend_reports,
        "inventory": {
            "devices": devices,
        },
        "summary": {
            "device_count": len(devices),
            "healthy_device_count": healthy_count,
            "partial_device_count": partial_count,
            "error_device_count": error_count,
            "overall_status": overall_status,
            "visibility_status": visibility_status,
            "warnings": warnings,
        },
    }
    return report


def build_doctor_report(args: argparse.Namespace, argv: list[str]) -> dict[str, Any]:
    overview_report = build_overview_report(args=args, argv=argv)
    findings: list[str] = []
    possible_causes: list[str] = []
    next_steps: list[str] = []

    summary = overview_report["summary"]
    environment = overview_report["environment"]
    backends = overview_report["backends"]
    devices = overview_report["inventory"]["devices"]
    torch_count = environment.get("torch_visible_device_count")
    visibility_controls = environment.get("visibility_controls", [])
    mismatch = summary["visibility_status"] == _VISIBLE_STATUS_MISMATCHED

    if mismatch and torch_count is not None:
        findings.append(
            f"PyTorch reports {torch_count} visible GPU(s), but Omnismi found {summary['device_count']}."
        )
        possible_causes.extend(
            [
                "The current runtime may expose framework-visible GPUs without the expected vendor telemetry path.",
                "Container or pod GPU device access may be incomplete.",
            ]
        )
        next_steps.extend(
            [
                "Confirm the current host, container, or pod has GPU device access.",
                "Compare `torch.cuda.device_count()` with `omnismi -o json`.",
            ]
        )

    if visibility_controls and (mismatch or summary["device_count"] == 0):
        possible_causes.append(
            "Runtime visibility controls may intentionally limit which devices the current process can see."
        )
        next_steps.append(
            "Review active visibility controls such as `CUDA_VISIBLE_DEVICES`, `NVIDIA_VISIBLE_DEVICES`, or `ROCR_VISIBLE_DEVICES` if you expected more devices."
        )

    relevant_missing_dependency = False
    for backend in backends:
        if backend["status"] == "error":
            findings.append(
                f"{backend['vendor'].upper()} backend `{backend['backend']}` reported an error."
            )
            if backend["reason"]:
                possible_causes.append(backend["reason"])
        elif backend["status"] == "missing_dependency" and (
            args.vendor == backend["vendor"] or mismatch
        ):
            relevant_missing_dependency = True
            findings.append(f"{backend['vendor'].upper()} backend is not installed in this environment.")

    if relevant_missing_dependency:
        possible_causes.append("A vendor backend dependency or userspace library is missing.")
        next_steps.append(
            "Install the matching Omnismi extra for the vendor you expect, such as `omnismi[nvidia]` or `omnismi[amd]`."
        )

    partial_devices = [device for device in devices if device["state"] == "PARTIAL"]
    error_devices = [device for device in devices if device["state"] == "ERROR"]

    for device in partial_devices:
        findings.append(f"Device {device['index']} has partial metrics or missing fields.")
    for device in error_devices:
        findings.append(f"Device {device['index']} could not provide usable info or metrics.")

    if partial_devices or error_devices:
        possible_causes.append(
            "Metrics can be partially unavailable because of runtime limits, permissions, or vendor API differences."
        )
        next_steps.append("Inspect the current runtime with `omnismi --wide` for per-device detail.")

    findings.extend(summary["warnings"])

    status = "OK"
    if error_devices or any(backend["status"] == "error" for backend in backends):
        status = "ERROR"
    elif findings:
        status = "WARN"

    if not findings and summary["device_count"] == 0:
        next_steps.append("No supported accelerators are visible in the current runtime.")
        next_steps.append("This is expected on CPU-only environments.")

    report = {
        "apiVersion": "omnismi/v1alpha1",
        "kind": "DoctorReport",
        "metadata": dict(overview_report["metadata"]),
        "command": {
            "argv": ["omnismi", *argv],
            "output": args.output,
        },
        "environment": environment,
        "backends": backends,
        "inventory": overview_report["inventory"],
        "summary": {
            "status": status,
            "finding_count": len(findings),
            "device_count": summary["device_count"],
            "visibility_status": summary["visibility_status"],
        },
        "findings": _unique_preserving_order(findings),
        "possible_causes": _unique_preserving_order(possible_causes),
        "next_steps": _unique_preserving_order(next_steps),
    }
    return report


def build_validate_spec_report(args: argparse.Namespace, argv: list[str]) -> dict[str, Any]:
    overview_report = build_overview_report(args=args, argv=argv)
    profile = get_profile(args.profile)
    if profile is None:
        raise ValueError(f"Unknown profile: {args.profile}")

    results: list[dict[str, Any]] = []
    summary_warnings = list(overview_report["summary"]["warnings"])

    for device in overview_report["inventory"]["devices"]:
        checks: list[dict[str, Any]] = []
        vendor_matches = device["vendor"] == profile.vendor
        checks.append(
            {
                "name": "vendor",
                "expected": profile.vendor,
                "observed": device["vendor"],
                "status": "PASS" if vendor_matches else "FAIL",
                "message": (
                    f"Vendor matches expected `{profile.vendor}`."
                    if vendor_matches
                    else f"Observed vendor `{device['vendor']}` does not match expected `{profile.vendor}`."
                ),
            }
        )

        alias_matches = profile_matches_device_name(profile, device.get("name"))
        if not vendor_matches:
            alias_status = "SKIP"
            alias_message = "Model alias check skipped because the vendor does not match."
        elif alias_matches:
            alias_status = "PASS"
            alias_message = f"Device name matches a curated alias for `{profile.name}`."
        else:
            alias_status = "WARN"
            alias_message = f"Device name did not match the curated aliases for `{profile.name}`."
        checks.append(
            {
                "name": "model_alias",
                "expected": profile.name,
                "observed": device.get("name"),
                "status": alias_status,
                "message": alias_message,
            }
        )

        observed_memory = device.get("memory_total_bytes") or device["metrics"].get("memory_total_bytes")
        if profile.memory_total_bytes is None:
            memory_status = "SKIP"
            memory_message = "The selected profile does not define an expected total-memory capacity."
        elif observed_memory is None:
            memory_status = "INCONCLUSIVE"
            memory_message = "The device did not report total-memory capacity."
        else:
            difference = abs(int(observed_memory) - int(profile.memory_total_bytes))
            if difference <= _PROFILE_MEMORY_TOLERANCE_BYTES:
                memory_status = "PASS"
                memory_message = (
                    f"Observed total memory is within {_format_bytes_compact(_PROFILE_MEMORY_TOLERANCE_BYTES)} of the expected capacity."
                )
            else:
                memory_status = "FAIL"
                memory_message = (
                    f"Observed total memory differs from the expected capacity by {_format_bytes_compact(difference)}."
                )
        checks.append(
            {
                "name": "memory_total_bytes",
                "expected": profile.memory_total_bytes,
                "observed": observed_memory,
                "status": memory_status,
                "message": memory_message,
            }
        )

        check_statuses = {check["status"] for check in checks}
        if "FAIL" in check_statuses:
            verdict_status = "FAIL"
        elif "WARN" in check_statuses:
            verdict_status = "WARN"
        elif "INCONCLUSIVE" in check_statuses:
            verdict_status = "INCONCLUSIVE"
        else:
            verdict_status = "PASS"

        results.append(
            {
                "device_index": device["index"],
                "device_name": device["name"],
                "device_vendor": device["vendor"],
                "device_state": device["state"],
                "observed_memory_total_bytes": observed_memory,
                "expected_memory_total_bytes": profile.memory_total_bytes,
                "verdict_status": verdict_status,
                "checks": checks,
            }
        )

        if device["state"] != "OK":
            summary_warnings.append(
                f"Device {device['index']} has `{device['state']}` telemetry; spec validation used limited evidence."
            )

    pass_count = sum(result["verdict_status"] == "PASS" for result in results)
    warn_count = sum(result["verdict_status"] == "WARN" for result in results)
    fail_count = sum(result["verdict_status"] == "FAIL" for result in results)
    inconclusive_count = sum(result["verdict_status"] == "INCONCLUSIVE" for result in results)

    overall_status = "INCONCLUSIVE"
    if results:
        if fail_count > 0:
            overall_status = "FAIL"
        elif warn_count > 0:
            overall_status = "WARN"
        elif inconclusive_count > 0:
            overall_status = "INCONCLUSIVE"
        else:
            overall_status = "PASS"
    if overall_status == "PASS" and summary_warnings:
        overall_status = "WARN"

    if not results:
        inconclusive_count = 1
        summary_warnings.append("No visible devices matched the current validation scope.")

    return {
        "apiVersion": "omnismi/v1alpha1",
        "kind": "ValidateSpecReport",
        "metadata": dict(overview_report["metadata"]),
        "command": {
            "argv": ["omnismi", *argv],
            "output": args.output,
        },
        "spec": {
            "profile": profile.name,
            "devices": sorted(_selected_device_indexes(args) or []),
            "all_devices": bool(args.all_devices),
            "vendor": args.vendor,
        },
        "environment": overview_report["environment"],
        "backends": overview_report["backends"],
        "inventory": overview_report["inventory"],
        "profile": profile_to_dict(profile),
        "results": results,
        "summary": {
            "status": overall_status,
            "device_count": len(results),
            "pass_count": pass_count,
            "warn_count": warn_count,
            "fail_count": fail_count,
            "inconclusive_count": inconclusive_count,
            "warnings": _unique_preserving_order(summary_warnings),
        },
    }


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def _render_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    lines = ["  ".join(header.ljust(widths[index]) for index, header in enumerate(headers))]
    for row in rows:
        lines.append("  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)))
    return "\n".join(lines)


def _supports_color(color_mode: str) -> bool:
    if color_mode == "never":
        return False
    if color_mode == "always":
        return True
    if not sys.stdout.isatty():
        return False
    if os.environ.get("TERM", "") == "dumb":
        return False
    return True


def _plain_text_width(value: str) -> int:
    return len(_ANSI_RE.sub("", value))


def _style(
    value: str,
    *,
    color: str | None = None,
    bold: bool = False,
    dim: bool = False,
    enabled: bool = False,
) -> str:
    if not enabled:
        return value

    codes: list[str] = []
    if bold:
        codes.append(_STYLE_CODES["bold"])
    if dim:
        codes.append(_STYLE_CODES["dim"])
    if color is not None:
        codes.append(_STYLE_CODES[color])
    if not codes:
        return value
    return "".join(codes) + value + _STYLE_RESET


def _status_color(status: str) -> str | None:
    if status in {"OK", "PASS", _VISIBLE_STATUS_MATCHED}:
        return "green"
    if status in {"WARN", "PARTIAL", _VISIBLE_STATUS_UNKNOWN, "EMPTY", "INCONCLUSIVE", "SKIP"}:
        return "yellow"
    if status in {"FAIL", "ERROR", _VISIBLE_STATUS_MISMATCHED}:
        return "red"
    return None


def _format_bytes_compact(value: int | None) -> str:
    if value is None:
        return "--"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(value)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)}{unit}"
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}PB"


def _format_uptime_compact(value: float | None) -> str | None:
    if value is None:
        return None

    remaining = int(value)
    days, remaining = divmod(remaining, 86400)
    hours, remaining = divmod(remaining, 3600)
    minutes, _ = divmod(remaining, 60)

    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def _format_memory_usage(used: int | None, total: int | None) -> str:
    if used is None and total is None:
        return "--"
    if total in (None, 0):
        return f"{_format_bytes_compact(used)} / --"
    percent = 0.0 if used is None else (float(used) / float(total)) * 100.0
    return f"{_format_bytes_compact(used)} / {_format_bytes_compact(total)} ({percent:.0f}%)"


def _format_memory_usage_compact(used: int | None, total: int | None, *, include_percent: bool) -> str:
    if used is None and total is None:
        return "--"
    if total in (None, 0):
        return f"{_format_bytes_compact(used)} / --"
    if not include_percent:
        return f"{_format_bytes_compact(used)} / {_format_bytes_compact(total)}"
    return _format_memory_usage(used, total)


def _format_rate(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{_format_bytes_compact(int(value))}/s"


def _format_visibility_controls(
    controls: list[dict[str, str]],
    *,
    include_values: bool,
) -> str:
    if not controls:
        return "none"

    parts: list[str] = []
    for control in controls:
        if include_values:
            parts.append(f"{control['name']}={control['value']}")
        else:
            parts.append(control["name"])
    return "; ".join(parts)


def _format_optional_count(value: int | None) -> str:
    if value is None:
        return "--"
    return str(value)


def _format_load_bar(value: float | None, *, enabled: bool) -> str:
    if value is None:
        return "[     ]"

    percent = max(0.0, min(100.0, float(value)))
    filled = int(round(percent / 20.0))
    bar = "[" + ("|" * filled) + (" " * (5 - filled)) + "]"
    color = "green"
    if percent >= 85.0:
        color = "red"
    elif percent >= 60.0:
        color = "yellow"
    return _style(bar, color=color, enabled=enabled)


def _truncate_text(value: str, width: int) -> str:
    if width <= 0:
        return ""
    if _plain_text_width(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return value[: width - 1] + "…"


def _pad_cell(value: str, width: int, *, align: str) -> str:
    padding = max(0, width - _plain_text_width(value))
    if align == "right":
        return (" " * padding) + value
    if align == "center":
        left = padding // 2
        right = padding - left
        return (" " * left) + value + (" " * right)
    return value + (" " * padding)


def _render_boxed_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    alignments: list[str],
) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], _plain_text_width(cell))

    header_line = "  " + "  ".join(
        _pad_cell(header, widths[index], align="left") for index, header in enumerate(headers)
    )
    inner_width = max(
        _plain_text_width(
            "  ".join(
                _pad_cell(row[index], widths[index], align=alignments[index])
                for index in range(len(headers))
            )
        )
        for row in rows
    ) if rows else _plain_text_width(
        "  ".join(_pad_cell(headers[index], widths[index], align="left") for index in range(len(headers)))
    )

    top = "┌" + ("─" * (inner_width + 2)) + "┐"
    bottom = "└" + ("─" * (inner_width + 2)) + "┘"

    body_lines = []
    for row in rows:
        text = "  ".join(
            _pad_cell(row[index], widths[index], align=alignments[index])
            for index in range(len(headers))
        )
        padding = " " * (inner_width - _plain_text_width(text))
        body_lines.append(f"│ {text}{padding} │")

    if not body_lines:
        body_lines.append(f"│ {'No visible devices'.ljust(inner_width)} │")

    return "\n".join([header_line, top, *body_lines, bottom])


def _build_overview_rows(
    devices: list[dict[str, Any]],
    *,
    wide: bool,
    color_enabled: bool,
    terminal_width: int,
) -> tuple[list[str], list[list[str]], list[str]]:
    if wide:
        show_temp = terminal_width >= 98
        show_power = terminal_width >= 90
        show_driver = terminal_width >= 100
        name_width = 22 if terminal_width >= 108 else 20 if terminal_width >= 100 else 18
    else:
        show_temp = terminal_width >= 84
        show_power = terminal_width >= 76
        show_driver = False
        name_width = 24 if terminal_width >= 104 else 20 if terminal_width >= 88 else 16

    include_memory_percent = terminal_width >= 92
    headers = ["ID", "NAME"]
    alignments = ["right", "left"]

    if show_temp:
        headers.append("TEMP")
        alignments.append("right")
    headers.extend(["LOAD", "MEMORY"])
    alignments.extend(["right", "right"])
    if show_power:
        headers.append("POWER")
        alignments.append("right")
    if show_driver:
        headers.append("DRIVER")
        alignments.append("left")
    headers.append("STATE")
    alignments.append("left")

    rows: list[list[str]] = []
    for device in devices:
        metrics = device["metrics"]
        row = [
            str(device["index"]),
            _truncate_text(device["name"], name_width),
        ]
        if show_temp:
            row.append(_format_temperature(metrics.get("temperature_c")))
        row.extend(
            [
                _format_load_bar(metrics.get("utilization_percent"), enabled=color_enabled),
                _format_memory_usage_compact(
                    metrics.get("memory_used_bytes"),
                    metrics.get("memory_total_bytes") or device.get("memory_total_bytes"),
                    include_percent=include_memory_percent,
                ),
            ]
        )
        if show_power:
            row.append(_format_power(metrics.get("power_w")))
        if show_driver:
            row.append(_truncate_text(device.get("driver") or "--", 12))
        row.append(
            _style(
                device["state"],
                color=_status_color(device["state"]),
                bold=device["state"] != "OK",
                enabled=color_enabled,
            )
        )
        rows.append(row)
    return headers, rows, alignments


def _format_vendor_summary(devices: list[dict[str, Any]]) -> str:
    if not devices:
        return "none"

    counts: dict[str, int] = {}
    for device in devices:
        vendor = device["vendor"]
        counts[vendor] = counts.get(vendor, 0) + 1
    return ", ".join(f"{vendor}({count})" for vendor, count in sorted(counts.items()))


def _render_heading(label: str, *, color_enabled: bool) -> str:
    return _style(label, color="blue", bold=True, enabled=color_enabled)


def _render_overview_table(report: dict[str, Any], wide: bool, color_mode: str) -> str:
    environment = report["environment"]
    system = report["system"]
    summary = report["summary"]
    devices = report["inventory"]["devices"]
    visibility_controls = environment.get("visibility_controls", [])
    backend_summary = " ".join(
        f"{item['backend']}:{item['status']}" for item in report["backends"]
    ) or "none"
    vendors = _format_vendor_summary(devices)
    color_enabled = _supports_color(color_mode=color_mode)
    terminal_width = max(72, min(shutil.get_terminal_size((100, 20)).columns - 1, 120))
    separator = " " + _style("─" * (terminal_width - 1), color="blue", dim=True, enabled=color_enabled)

    header_parts = [
        _style("Omnismi", color="cyan", bold=True, enabled=color_enabled),
        f"v{report['metadata']['omnismi_version']}",
        f"[Host: {environment['hostname']}]",
    ]
    if system.get("ip_address") is not None:
        header_parts.append(f"[IP: {system['ip_address']}]")
    uptime_text = _format_uptime_compact(system.get("uptime_seconds"))
    if uptime_text is not None:
        header_parts.append(f"[Uptime: {uptime_text}]")
    header_parts.append(
        f"[Status: {_style(summary['overall_status'], color=_status_color(summary['overall_status']), bold=True, enabled=color_enabled)}]"
    )

    system_parts: list[str] = []
    system_parts.append(
        "CPU: "
        + (
            _format_percent(system.get("cpu_percent"))
            if system.get("cpu_percent") is not None
            else "--"
        )
    )
    if system.get("memory_total_bytes") is not None:
        system_parts.append(
            "Mem: "
            + f"{_format_bytes_compact(system.get('memory_used_bytes'))}/{_format_bytes_compact(system.get('memory_total_bytes'))}"
        )
    else:
        system_parts.append("Mem: --")
    if system.get("net_rx_bytes_per_s") is not None or system.get("net_tx_bytes_per_s") is not None:
        system_parts.append(
            f"Net: ↓{_format_rate(system.get('net_rx_bytes_per_s'))} ↑{_format_rate(system.get('net_tx_bytes_per_s'))}"
        )
    system_parts.append(f"Driver: {system['driver_label']}")

    visible_parts = [
        f"Devices: {summary['device_count']}",
        f"Vendors: {vendors}",
        f"Scope: {environment['execution_scope']}",
    ]
    if wide:
        visible_parts.append(f"Backends: {backend_summary}")
    elif environment.get("torch_visible_device_count") is not None:
        visible_parts.append(f"Torch: {environment['torch_visible_device_count']}")
    if visibility_controls and not wide:
        visible_parts.append(
            f"Filters: {_format_visibility_controls(visibility_controls, include_values=False)}"
        )

    lines = [
        " ".join(header_parts),
        separator,
        f" {_render_heading('[SYSTEM]', color_enabled=color_enabled)} " + " | ".join(system_parts),
        f" {_render_heading('[VISIBLE]', color_enabled=color_enabled)} " + " | ".join(visible_parts),
        separator,
        "",
    ]

    if devices:
        headers, rows, alignments = _build_overview_rows(
            devices=devices,
            wide=wide,
            color_enabled=color_enabled,
            terminal_width=terminal_width,
        )
        styled_headers = [
            _style(header, color="blue", bold=True, enabled=color_enabled) for header in headers
        ]
        lines.append(_render_boxed_table(headers=styled_headers, rows=rows, alignments=alignments))
    else:
        lines.append(" No supported accelerators are visible in the current runtime.")

    warnings = list(summary["warnings"])
    if wide:
        lines.extend(
            [
                "",
                "Runtime:",
                f"- execution_scope={environment['execution_scope']}",
                f"- orchestrator={environment['orchestrator']}",
                f"- visibility_scope={environment['visibility_scope']}",
                f"- torch_visible_device_count={_format_optional_count(environment.get('torch_visible_device_count'))}",
                f"- visibility_controls={_format_visibility_controls(visibility_controls, include_values=True)}",
                f"- backend_status={backend_summary}",
            ]
        )

    if warnings:
        lines.extend(["", _render_heading("Warnings:", color_enabled=color_enabled)])
        lines.extend(f"- {warning}" for warning in warnings)
    elif not devices:
        lines.extend(
            [
                "",
                _render_heading("Hints:", color_enabled=color_enabled),
                "- This is expected on CPU-only environments.",
                "- Run `omnismi doctor` to inspect backend imports and runtime visibility.",
            ]
        )
    elif not wide:
        lines.extend(
            [
                "",
                _render_heading("Tips:", color_enabled=color_enabled),
                "- Run `omnismi --wide` for driver and runtime detail.",
                "- Run `omnismi doctor` if visibility or metrics look wrong.",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def _render_doctor_table(report: dict[str, Any], verbose: bool, *, color_mode: str) -> str:
    environment = report["environment"]
    summary = report["summary"]
    visibility_controls = environment.get("visibility_controls", [])
    color_enabled = _supports_color(color_mode=color_mode)
    separator = " " + _style("─" * 79, color="blue", dim=True, enabled=color_enabled)
    lines = [
        (
            f"{_style('Omnismi Doctor', color='cyan', bold=True, enabled=color_enabled)} "
            f"v{report['metadata']['omnismi_version']} "
            f"[Host: {environment['hostname']}] "
            f"[Scope: {environment['execution_scope']}] "
            f"[Status: {_style(summary['status'], color=_status_color(summary['status']), bold=True, enabled=color_enabled)}]"
        ),
        "",
        separator,
        _render_heading("[FINDINGS]", color_enabled=color_enabled),
    ]

    if report["findings"]:
        lines.extend(f"- {finding}" for finding in report["findings"])
    else:
        lines.append("- No major discovery or visibility issues were detected.")

    if report["possible_causes"]:
        lines.extend(["", _render_heading("[POSSIBLE CAUSES]", color_enabled=color_enabled)])
        lines.extend(f"- {cause}" for cause in report["possible_causes"])

    if report["backends"] and (verbose or report["findings"]):
        lines.extend(["", _render_heading("[BACKENDS]", color_enabled=color_enabled)])
        for backend in report["backends"]:
            detail = f"- {backend['vendor']} / {backend['backend']}: {backend['status']}"
            if backend["reason"]:
                detail += f'  reason="{backend["reason"]}"'
            lines.append(detail)

    lines.extend(
        [
            "",
            _render_heading("[RUNTIME]", color_enabled=color_enabled),
            f"- execution_scope={environment['execution_scope']}",
            f"- orchestrator={environment['orchestrator']}",
            f"- visibility_scope={environment['visibility_scope']}",
            f"- torch_visible_device_count={_format_optional_count(environment.get('torch_visible_device_count'))}",
            f"- visibility_controls={_format_visibility_controls(visibility_controls, include_values=True)}",
        ]
    )

    if report["next_steps"]:
        lines.extend(["", _render_heading("[NEXT STEPS]", color_enabled=color_enabled)])
        lines.extend(f"- {step}" for step in report["next_steps"])

    return "\n".join(lines).rstrip() + "\n"


def _render_validate_spec_table(
    report: dict[str, Any],
    *,
    verbose: bool,
    color_mode: str,
) -> str:
    environment = report["environment"]
    profile = report["profile"]
    summary = report["summary"]
    color_enabled = _supports_color(color_mode=color_mode)
    separator = " " + _style("─" * 79, color="blue", dim=True, enabled=color_enabled)

    lines = [
        (
            f"{_style('Omnismi Validate Spec', color='cyan', bold=True, enabled=color_enabled)} "
            f"v{report['metadata']['omnismi_version']} "
            f"[Host: {environment['hostname']}] "
            f"[Profile: {profile['name']}] "
            f"[Status: {_style(summary['status'], color=_status_color(summary['status']), bold=True, enabled=color_enabled)}]"
        ),
        "",
        separator,
        _render_heading("[PROFILE]", color_enabled=color_enabled),
        f"- vendor={profile['vendor']}",
        f"- description={profile['description']}",
        f"- expected_memory_total_bytes={_format_bytes(profile['memory_total_bytes'])}",
        f"- memory_class={profile['memory_class'] or '--'}",
        f"- bandwidth_class={profile['bandwidth_class'] or '--'}",
        f"- visibility_scope={environment['visibility_scope']}",
    ]

    rows: list[list[str]] = []
    for result in report["results"]:
        rows.append(
            [
                str(result["device_index"]),
                _truncate_text(result["device_name"], 24),
                result["device_vendor"],
                _format_memory_pair(
                    result["observed_memory_total_bytes"],
                    result["expected_memory_total_bytes"],
                ),
                _style(
                    result["verdict_status"],
                    color=_status_color(result["verdict_status"]),
                    bold=result["verdict_status"] != "PASS",
                    enabled=color_enabled,
                ),
            ]
        )

    lines.extend(
        [
            "",
            _render_heading("[RESULTS]", color_enabled=color_enabled),
            _render_boxed_table(
                headers=[
                    _style("ID", color="blue", bold=True, enabled=color_enabled),
                    _style("NAME", color="blue", bold=True, enabled=color_enabled),
                    _style("VENDOR", color="blue", bold=True, enabled=color_enabled),
                    _style("MEMORY", color="blue", bold=True, enabled=color_enabled),
                    _style("VERDICT", color="blue", bold=True, enabled=color_enabled),
                ],
                rows=rows,
                alignments=["right", "left", "left", "right", "left"],
            ),
        ]
    )

    if verbose and report["results"]:
        lines.extend(["", _render_heading("[CHECKS]", color_enabled=color_enabled)])
        for result in report["results"]:
            lines.append(
                f"- device {result['device_index']} `{result['device_name']}` => {result['verdict_status']}"
            )
            for check in result["checks"]:
                lines.append(f"  {check['name']}: {check['status']} - {check['message']}")

    if report["summary"]["warnings"]:
        lines.extend(["", _render_heading("[WARNINGS]", color_enabled=color_enabled)])
        lines.extend(f"- {warning}" for warning in report["summary"]["warnings"])

    lines.extend(
        [
            "",
            _render_heading("[SUMMARY]", color_enabled=color_enabled),
            f"- pass_count={summary['pass_count']}",
            f"- warn_count={summary['warn_count']}",
            f"- fail_count={summary['fail_count']}",
            f"- inconclusive_count={summary['inconclusive_count']}",
        ]
    )

    return "\n".join(lines).rstrip() + "\n"


def _render_structured_output(report: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(report, indent=2, sort_keys=False) + "\n"
    if output_format == "yaml":
        return _dump_yaml(report) + "\n"
    raise ValueError(f"Unsupported output format: {output_format}")


def _dump_yaml(value: Any, indent: int = 0) -> str:
    if isinstance(value, dict):
        return _dump_yaml_mapping(value, indent)
    if isinstance(value, list):
        return _dump_yaml_sequence(value, indent)
    return (" " * indent) + _yaml_scalar(value)


def _dump_yaml_mapping(value: dict[str, Any], indent: int) -> str:
    lines: list[str] = []
    padding = " " * indent

    for key, item in value.items():
        if isinstance(item, dict):
            if item:
                lines.append(f"{padding}{key}:")
                lines.append(_dump_yaml_mapping(item, indent + 2))
            else:
                lines.append(f"{padding}{key}: {{}}")
        elif isinstance(item, list):
            if item:
                lines.append(f"{padding}{key}:")
                lines.append(_dump_yaml_sequence(item, indent + 2))
            else:
                lines.append(f"{padding}{key}: []")
        else:
            lines.append(f"{padding}{key}: {_yaml_scalar(item)}")

    return "\n".join(lines)


def _dump_yaml_sequence(value: list[Any], indent: int) -> str:
    lines: list[str] = []
    padding = " " * indent

    for item in value:
        if isinstance(item, dict):
            if not item:
                lines.append(f"{padding}- {{}}")
                continue
            first = True
            for key, nested in item.items():
                prefix = f"{padding}- " if first else f"{padding}  "
                if isinstance(nested, dict):
                    if nested:
                        lines.append(f"{prefix}{key}:")
                        lines.append(_dump_yaml_mapping(nested, indent + 4))
                    else:
                        lines.append(f"{prefix}{key}: {{}}")
                elif isinstance(nested, list):
                    if nested:
                        lines.append(f"{prefix}{key}:")
                        lines.append(_dump_yaml_sequence(nested, indent + 4))
                    else:
                        lines.append(f"{prefix}{key}: []")
                else:
                    lines.append(f"{prefix}{key}: {_yaml_scalar(nested)}")
                first = False
        elif isinstance(item, list):
            if item:
                lines.append(f"{padding}-")
                lines.append(_dump_yaml_sequence(item, indent + 2))
            else:
                lines.append(f"{padding}- []")
        else:
            lines.append(f"{padding}- {_yaml_scalar(item)}")

    return "\n".join(lines)


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value)

    text = str(value)
    needs_quotes = (
        text == ""
        or text != text.strip()
        or any(char in text for char in (":", "#", "{", "}", "[", "]", ",", '"', "'"))
    )
    if needs_quotes:
        return json.dumps(text)
    return text


def _emit_overview(report: dict[str, Any], args: argparse.Namespace) -> str:
    if args.output == "table":
        return _render_overview_table(report=report, wide=bool(args.wide), color_mode=str(args.color))
    return _render_structured_output(report=report, output_format=args.output)


def _run_overview(args: argparse.Namespace, argv: list[str]) -> int:
    if args.watch and args.output != "table":
        print("--watch is only supported with the default table output.", file=sys.stderr)
        return 2

    if args.watch:
        try:
            while True:
                report = build_overview_report(args=args, argv=argv)
                sys.stdout.write("\x1b[2J\x1b[H")
                sys.stdout.write(_emit_overview(report=report, args=args))
                sys.stdout.flush()
                time.sleep(1.0)
        except KeyboardInterrupt:
            return 0

    report = build_overview_report(args=args, argv=argv)
    sys.stdout.write(_emit_overview(report=report, args=args))
    return 0


def _run_doctor(args: argparse.Namespace, argv: list[str]) -> int:
    report = build_doctor_report(args=args, argv=argv)
    if args.output == "table":
        sys.stdout.write(
            _render_doctor_table(
                report=report,
                verbose=bool(args.verbose),
                color_mode=str(args.color),
            )
        )
    else:
        sys.stdout.write(_render_structured_output(report=report, output_format=args.output))
    return 0


def _run_validate_spec(args: argparse.Namespace, argv: list[str]) -> int:
    profile = get_profile(args.profile)
    if profile is None:
        available = ", ".join(item.name for item in list_profiles())
        print(
            f"Unknown profile `{args.profile}`. Available profiles: {available}",
            file=sys.stderr,
        )
        return 2

    report = build_validate_spec_report(args=args, argv=argv)
    if args.output == "table":
        sys.stdout.write(
            _render_validate_spec_table(
                report=report,
                verbose=bool(args.verbose),
                color_mode=str(args.color),
            )
        )
    else:
        sys.stdout.write(_render_structured_output(report=report, output_format=args.output))
    return 0


def _run_placeholder(command_name: str) -> int:
    print(
        f"`omnismi {command_name}` is planned but not implemented yet.",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)

    if raw_args and raw_args[0] in _SUBCOMMANDS:
        parser = build_root_parser()
        args = parser.parse_args(raw_args)
        if args.command == "doctor":
            return _run_doctor(args=args, argv=raw_args)
        if args.command == "bench":
            return _run_placeholder("bench")
        if args.command == "validate-spec":
            return _run_validate_spec(args=args, argv=raw_args)
        parser.error(f"Unsupported command: {args.command}")

    parser = build_overview_parser()
    args = parser.parse_args(raw_args)
    return _run_overview(args=args, argv=raw_args)
