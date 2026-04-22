"""Command-line interface for Omnismi."""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import omnismi as omi
from omnismi import __version__
from omnismi.backends import registered_backends

_SUBCOMMANDS = {"doctor", "bench", "validate-spec"}
_BACKEND_NAMES = {
    "NvidiaBackend": "nvml",
    "AmdBackend": "amdsmi",
    "GoogleTpuBackend": "tpumonitoring",
}
_VISIBLE_STATUS_MATCHED = "MATCHED"
_VISIBLE_STATUS_MISMATCHED = "MISMATCHED"
_VISIBLE_STATUS_UNKNOWN = "UNKNOWN"


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
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Reserved for future color control. Current output is plain text.",
    )
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
    doctor_parser.add_argument(
        "--no-color",
        action="store_true",
        help="Reserved for future color control. Current output is plain text.",
    )

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
    validate_parser.add_argument(
        "--profile",
        help="Planned hardware profile name.",
    )

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

    return {
        "platform": platform.system().lower(),
        "hostname": socket.gethostname(),
        "execution_scope": execution_scope,
        "orchestrator": orchestrator,
        "torch_visible_device_count": _torch_visible_device_count(),
    }


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
    return f"{value:.0f}C"


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


def _render_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    lines = ["  ".join(header.ljust(widths[index]) for index, header in enumerate(headers))]
    for row in rows:
        lines.append("  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)))
    return "\n".join(lines)


def _render_overview_table(report: dict[str, Any], wide: bool) -> str:
    environment = report["environment"]
    summary = report["summary"]
    devices = report["inventory"]["devices"]
    backend_summary = " ".join(
        f"{item['backend']}:{item['status']}" for item in report["backends"]
    ) or "none"
    vendors = ",".join(sorted({device["vendor"] for device in devices})) or "none"

    header = (
        f"Omnismi {report['metadata']['omnismi_version']}  "
        f"host={environment['hostname']}  "
        f"env={environment['execution_scope']}  "
        f"status={summary['overall_status']}"
    )
    if wide and environment.get("orchestrator") not in (None, "none"):
        header = (
            f"Omnismi {report['metadata']['omnismi_version']}  "
            f"host={environment['hostname']}  "
            f"env={environment['execution_scope']}  "
            f"orchestrator={environment['orchestrator']}  "
            f"status={summary['overall_status']}"
        )
    lines = [header]

    visibility_line = f"Visible accelerators: {summary['device_count']}  vendors={vendors}"
    if wide:
        visibility_line += f"  backends={backend_summary}"
    else:
        visibility_line += "  scope=runtime-visible"
    lines.append(visibility_line)
    lines.append("")

    if devices:
        if wide:
            headers = [
                "INDEX",
                "VENDOR",
                "NAME",
                "UUID",
                "DRIVER",
                "MEM",
                "UTIL",
                "TEMP",
                "POWER",
                "CORECLK",
                "MEMCLK",
                "STATE",
            ]
            rows = [
                [
                    str(device["index"]),
                    device["vendor"],
                    device["name"],
                    device["uuid"] or "-",
                    device["driver"] or "-",
                    _format_memory_pair(
                        device["metrics"].get("memory_used_bytes"),
                        device["metrics"].get("memory_total_bytes") or device.get("memory_total_bytes"),
                    ),
                    _format_percent(device["metrics"].get("utilization_percent")),
                    _format_temperature(device["metrics"].get("temperature_c")),
                    _format_power(device["metrics"].get("power_w")),
                    _format_clock(device["metrics"].get("core_clock_mhz")),
                    _format_clock(device["metrics"].get("memory_clock_mhz")),
                    device["state"],
                ]
                for device in devices
            ]
        else:
            headers = ["INDEX", "VENDOR", "NAME", "MEM", "UTIL", "TEMP", "POWER", "STATE"]
            rows = [
                [
                    str(device["index"]),
                    device["vendor"],
                    device["name"],
                    _format_memory_pair(
                        device["metrics"].get("memory_used_bytes"),
                        device["metrics"].get("memory_total_bytes") or device.get("memory_total_bytes"),
                    ),
                    _format_percent(device["metrics"].get("utilization_percent")),
                    _format_temperature(device["metrics"].get("temperature_c")),
                    _format_power(device["metrics"].get("power_w")),
                    device["state"],
                ]
                for device in devices
            ]
        lines.append(_render_table(headers=headers, rows=rows))
    else:
        lines.append("No supported accelerators are visible in the current runtime.")

    warnings = list(summary["warnings"])
    if wide and environment.get("torch_visible_device_count") is not None:
        lines.extend(
            [
                "",
                "Runtime:",
                f"- execution_scope={environment['execution_scope']}",
                f"- torch_visible_device_count={environment['torch_visible_device_count']}",
                f"- backend_status={backend_summary}",
            ]
        )

    if warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in warnings)
    elif not devices:
        lines.extend(
            [
                "",
                "Hints:",
                "- This is expected on CPU-only environments.",
                "- Run `omnismi doctor` to inspect backend imports and runtime visibility.",
            ]
        )
    elif not wide:
        lines.extend(
            [
                "",
                "Tips:",
                "- Run `omnismi --wide` for more columns.",
                "- Run `omnismi doctor` if visibility or metrics look wrong.",
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
        return _render_overview_table(report=report, wide=bool(args.wide))
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
            return _run_placeholder("doctor")
        if args.command == "bench":
            return _run_placeholder("bench")
        if args.command == "validate-spec":
            return _run_placeholder("validate-spec")
        parser.error(f"Unsupported command: {args.command}")

    parser = build_overview_parser()
    args = parser.parse_args(raw_args)
    return _run_overview(args=args, argv=raw_args)
