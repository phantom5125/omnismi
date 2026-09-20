"""Build one-shot accelerator preflight snapshots for agents."""

from __future__ import annotations

import time
from typing import Any

from omnismi.api import gpus as list_gpus
from omnismi.visibility import filter_gpus_by_visibility

SCHEMA_VERSION = 1


def _memory_free_bytes(used: int | None, total: int | None) -> int | None:
    if used is None or total is None:
        return None
    free = total - used
    return free if free >= 0 else None


def device_snapshot(
    device: Any, *, logical_index: int, realtime: bool = True
) -> dict[str, Any]:
    """Serialize one device for JSON output."""
    info = device.info()
    if realtime:
        with device.realtime():
            metrics = device.metrics()
    else:
        metrics = device.metrics()

    total = metrics.memory_total_bytes
    if total is None:
        total = info.memory_total_bytes
    used = metrics.memory_used_bytes
    free = _memory_free_bytes(used, total)

    return {
        "logical_index": logical_index,
        "physical_index": int(device.index),
        "vendor": info.vendor,
        "name": info.name,
        "uuid": info.uuid,
        "driver": info.driver,
        "memory_total_bytes": total,
        "memory_used_bytes": used,
        "memory_free_bytes": free,
        "utilization_percent": metrics.utilization_percent,
        "temperature_c": metrics.temperature_c,
        "power_w": metrics.power_w,
        "processes": [],
    }


def build_preflight(
    *,
    min_gpus: int = 0,
    min_free_bytes: int | None = None,
    require_idle: bool = False,
    visible_only: bool = True,
    include_topology: bool = False,
    devices: list[Any] | None = None,
) -> dict[str, Any]:
    """Return a preflight snapshot dict including exit_code semantics."""
    warnings: list[str] = []
    failures: list[dict[str, Any]] = []

    try:
        all_devices = list(devices) if devices is not None else list_gpus()
        selected, visibility = filter_gpus_by_visibility(
            all_devices, visible_only=visible_only
        )
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "schema_version": SCHEMA_VERSION,
            "command": "preflight",
            "ok": False,
            "exit_code": 10,
            "ts_ns": time.time_ns(),
            "error": f"backend_error: {exc}",
            "warnings": warnings,
            "failures": [{"code": "backend_error", "message": str(exc)}],
            "devices": [],
            "topology_included": False,
            "metrics_mode": "snapshot_realtime",
        }

    device_rows: list[dict[str, Any]] = []
    for logical_index, device in enumerate(selected):
        try:
            device_rows.append(
                device_snapshot(device, logical_index=logical_index, realtime=True)
            )
        except Exception as exc:
            warnings.append(
                f"device {getattr(device, 'index', '?')} snapshot failed: {exc}"
            )

    if not device_rows:
        failures.append(
            {"code": "no_accelerators", "message": "no visible accelerators"}
        )

    if min_gpus > 0 and len(device_rows) < min_gpus:
        failures.append(
            {
                "code": "insufficient_gpu_count",
                "have": len(device_rows),
                "need": min_gpus,
            }
        )

    if min_free_bytes is not None and device_rows:
        for row in device_rows:
            free = row.get("memory_free_bytes")
            if free is None:
                warnings.append(
                    f"logical_index {row['logical_index']}: memory_free_bytes unknown; "
                    "min-free check skipped for this device"
                )
                continue
            if free < min_free_bytes:
                failures.append(
                    {
                        "code": "insufficient_free_memory",
                        "device_logical_index": row["logical_index"],
                        "have_free_bytes": free,
                        "need_free_bytes": min_free_bytes,
                    }
                )

    if require_idle:
        warnings.append(
            "processes API not implemented; --require-idle not enforced"
        )

    if include_topology:
        warnings.append("topology API not implemented; topology omitted")

    free_values = [
        row["memory_free_bytes"]
        for row in device_rows
        if row.get("memory_free_bytes") is not None
    ]
    vendors = sorted({row["vendor"] for row in device_rows})

    if not device_rows:
        exit_code = 2
    elif any(
        f.get("code") in {"insufficient_gpu_count", "insufficient_free_memory"}
        for f in failures
    ):
        exit_code = 3
    else:
        exit_code = 0

    return {
        "schema_version": SCHEMA_VERSION,
        "command": "preflight",
        "ok": exit_code == 0,
        "exit_code": exit_code,
        "ts_ns": time.time_ns(),
        "visibility": {
            "mode": visibility.mode,
            "env": visibility.env,
            "physical_indices": visibility.physical_indices,
            "logical_indices": visibility.logical_indices,
        },
        "requirements": {
            "min_gpus": min_gpus,
            "min_free_bytes_per_gpu": min_free_bytes,
            "require_idle": require_idle,
            "require_idle_enforced": False,
        },
        "summary": {
            "gpu_count": len(device_rows),
            "vendors": vendors,
            "all_free_bytes_min": min(free_values) if free_values else None,
            "busy_gpu_count": None,
        },
        "devices": device_rows,
        "failures": failures,
        "warnings": warnings,
        "topology_included": False,
        "metrics_mode": "snapshot_realtime",
        "notes": [
            "preflight uses one-shot realtime metric reads",
            "processes and topology are not implemented in this release",
            "framework tensor allocator state is out of scope",
        ],
    }


def build_inventory(*, visible_only: bool = True) -> dict[str, Any]:
    """Inventory-only snapshot (no threshold gates beyond empty)."""
    result = build_preflight(visible_only=visible_only)
    result["command"] = "inventory"
    if result.get("devices"):
        result["ok"] = True
        result["exit_code"] = 0
        result["failures"] = []
    return result
