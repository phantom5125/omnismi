"""Read documented AMD RAS counter files, preserving identity and snapshot scope."""

from __future__ import annotations

from itertools import islice
from pathlib import Path
from typing import Any

from omnismi.diagnostics.engine import diagnose
from omnismi.identity import normalize_bdf


def collect_ras(sys_root: str | Path = "/sys") -> dict[str, Any]:
    result: dict[str, Any] = {"reports": [], "limitations": [], "status": "unavailable"}
    root = Path(sys_root) / "bus/pci/devices"
    try:
        devices = list(islice(root.iterdir(), 4097))
        if len(devices) > 4096:
            result["limitations"].append("PCI enumeration truncated")
        for device in devices[:4096]:
            try:
                with (device / "vendor").open() as stream:
                    if stream.read(32).strip().lower() != "0x1002":
                        continue
                address = normalize_bdf(device.name)
                counters = list(islice((device / "ras").glob("*_err_count"), 257))
                if len(counters) > 256:
                    result["limitations"].append(
                        f"RAS block enumeration truncated: {address}"
                    )
                for path in counters[:256]:
                    with path.open() as stream:
                        text = stream.read(4097)
                    if len(text) > 4096:
                        raise ValueError("RAS counter file is oversized")
                    block = path.name.removesuffix("_err_count")
                    report = diagnose(
                        text, input_format="ras", block=block, pci_address=address
                    )
                    prefix = f"ras:{address}:{block}:"
                    for evidence in report["evidence"]:
                        evidence["id"] = prefix + evidence["id"]
                        evidence["collector"] = "linux_amdgpu_ras_sysfs"
                    for finding in report["data"]["findings"]:
                        finding["evidence_ids"] = [
                            prefix + eid for eid in finding["evidence_ids"]
                        ]
                    result["reports"].append(report)
            except (OSError, ValueError) as exc:
                result["limitations"].append(f"{device.name}: {exc}")
    except OSError as exc:
        result["limitations"].append(str(exc))
    if result["reports"]:
        result["status"] = "partial" if result["limitations"] else "ok"
    return result
