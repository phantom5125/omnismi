"""One bounded passive call combines kernel evidence and device telemetry."""

from __future__ import annotations

import contextlib
import json
import math
import sys
from dataclasses import asdict
from typing import Any

from omnismi.backends.command import query_text
from omnismi.backends.registry import registered_backends
from omnismi.diagnostics.collectors import collect_kernel_log
from omnismi.diagnostics.engine import decode_error, diagnose
from omnismi.diagnostics.ras import collect_ras
from omnismi.errors import BackendError


def collect_snapshot(vendor: str | None = None) -> dict[str, Any]:
    """Worker implementation; parent bounds all SDK calls, including hangs."""
    kernel = collect_kernel_log(timeout=3)
    report = diagnose(kernel.pop("text"))
    report["scope"]["input_kind"] = "passive_hardware_snapshot"
    report["scope"]["visibility"] = "management_devices_not_runtime_ordinals"
    report["data"]["kernel_collection"] = kernel
    devices, collections = [], []
    for backend in registered_backends():
        if vendor is not None and backend.vendor != vendor:
            continue
        entry = {"vendor": backend.vendor, "status": "unavailable", "reason": None}
        collections.append(entry)
        try:
            if not backend.available():
                entry["reason"] = (
                    "dependency_missing"
                    if getattr(backend, "_import_failed", False)
                    else "no_management_devices"
                )
                continue
            for index, handle in enumerate(backend.devices()):
                info = asdict(backend.info(handle, index))
                metrics = asdict(backend.metrics(handle, index))
                item = {
                    "info": info,
                    "metrics": metrics,
                    "index_scope": f"{backend.vendor}_snapshot_only",
                }
                # CNDEV returns native codes for individual unavailable fields.
                records = getattr(backend, "_records", {})
                if backend.vendor == "cambricon":
                    item["return_codes"] = records.get(handle, {}).get(
                        "return_codes", {}
                    )
                if backend.vendor == "alibaba":
                    record = records.get(handle, {})
                    telemetry = getattr(backend, "_telemetry", {}).get(
                        record.get("pci_address"), {}
                    )
                    item["telemetry_error"] = getattr(backend, "_telemetry_error", None)
                    if record.get("uuid") and record["uuid"] == telemetry.get("uuid"):
                        item["ecc_counters"] = telemetry.get("ecc", {})
                        item["ecc_semantics"] = "historical_snapshots_not_deltas"
                        for key, value in item["ecc_counters"].items():
                            if value is not None and value > 0:
                                domain, correction = key.split("/")[1].lower().split()
                                finding = decode_error(
                                    "alibaba", "ecc", f"{domain}-{correction}"
                                )["data"]["findings"][0]
                                finding.update(
                                    assessment="observed_counter_snapshot",
                                    count=value,
                                    count_semantics=key.split("/")[0].lower()
                                    + "_snapshot_not_delta",
                                    pci_address=record["pci_address"],
                                    uuid=record["uuid"],
                                    evidence_ids=[f"ppu-ecc:{record['uuid']}:{key}"],
                                )
                                report["data"]["findings"].append(finding)
                                report["evidence"].append(
                                    {
                                        "id": finding["evidence_ids"][0],
                                        "collector": "ppu-smi -q",
                                        "counter": key,
                                        "value": value,
                                    }
                                )
                        report["sources"].append(
                            {
                                "id": "alibaba-ppu-smi",
                                "url": "https://developer.t-head.cn/docs_center/doc_detail/index.html?projectId=39&chapterId=221",
                            }
                        )
                devices.append(item)
            entry["status"] = "ok"
        except Exception as exc:
            entry.update(status="error", reason=str(exc))
        finally:
            try:
                backend.close()
            except Exception as exc:
                entry.update(status="error", reason=f"cleanup_failed: {exc}")
    if vendor in {None, "amd"}:
        ras = collect_ras()
        report["data"]["ras_collection"] = {
            key: value for key, value in ras.items() if key != "reports"
        }
        for observed in ras["reports"]:
            report["data"]["findings"].extend(observed["data"]["findings"])
            report["evidence"].extend(observed["evidence"])
            report["sources"].extend(observed["sources"])
    report["sources"] = list(
        {source["id"]: source for source in report["sources"]}.values()
    )
    report["data"].update(devices=devices, backend_collections=collections)
    findings = report["data"]["findings"]
    statuses = {finding["status"] for finding in findings}
    report["status"] = (
        "FAIL"
        if "FAIL" in statuses
        else "WARN" if "WARN" in statuses else "INCONCLUSIVE"
    )
    report["data"]["coverage"]["recognized"] = sum(
        f.get("recognized", False) for f in findings
    )
    report["limitations"].append(
        "Management telemetry and historical counts do not prove current health."
    )
    if kernel["status"] != "ok" or any(item["status"] != "ok" for item in collections):
        report["limitations"].append(
            "One or more passive collectors were unavailable or incomplete."
        )
    return report


def collect_hardware(
    *, vendor: str | None = None, timeout: float = 30
) -> dict[str, Any]:
    if vendor not in {None, "nvidia", "amd", "google", "alibaba", "cambricon"}:
        raise ValueError("Unknown hardware vendor")
    if not math.isfinite(timeout) or not 0 < timeout <= 600:
        raise ValueError("Hardware collection timeout must be in (0, 600]")
    try:
        return json.loads(
            query_text(
                [sys.executable, "-m", "omnismi.diagnostics.hardware", vendor or "all"],
                timeout=timeout,
            )
        )
    except (OSError, ValueError, BackendError) as exc:
        report = diagnose("")
        report["scope"]["input_kind"] = "passive_hardware_snapshot"
        report["data"]["collection"] = {"status": "incomplete", "reason": str(exc)}
        report["limitations"].append(
            "Hardware collection did not complete; no health verdict is available."
        )
        return report


if __name__ == "__main__":
    with contextlib.redirect_stdout(sys.stderr):
        result = collect_snapshot(None if sys.argv[1] == "all" else sys.argv[1])
    print(json.dumps(result, allow_nan=False, separators=(",", ":")))
