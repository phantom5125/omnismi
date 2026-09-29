"""Read-only Linux locality discovery and constrained affinity suggestions."""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path
from typing import Any

from omnismi import __version__

_BDF = re.compile(r"^[0-9a-f]{4}:[0-9a-f]{2}:[0-1][0-9a-f]\.[0-7]$", re.I)


def parse_cpu_list(value: str) -> list[int]:
    """Expand Linux list syntax, bounded to 65536 CPU/node identifiers."""
    if not isinstance(value, str) or len(value) > 65536:
        raise ValueError("Invalid CPU/node list")
    ids: set[int] = set()
    if not value.strip():
        return []
    for part in value.strip().split(","):
        if not re.fullmatch(r"\d+(?:-\d+)?", part):
            raise ValueError("Invalid CPU/node list")
        limits = [int(x) for x in part.split("-")]
        first, last = limits[0], limits[-1]
        if first > last or last > 65535:
            raise ValueError("CPU/node list is reversed or too large")
        ids.update(range(first, last + 1))
    return sorted(ids)


def _read(path: Path) -> str | None:
    try:
        with path.open() as stream:
            text = stream.read(65537)
        return text.strip() if len(text) <= 65536 else None
    except (OSError, UnicodeError):
        return None


def _number(text: str | None, base: int = 10) -> int | None:
    try:
        return int(text, base) if text is not None else None
    except ValueError:
        return None


def _ids(text: str | None) -> list[int] | None:
    try:
        return parse_cpu_list(text) if text is not None else None
    except ValueError:
        return None


def _entries(path: Path, limit: int, problems: list[str]) -> list[Path]:
    try:
        items = list(islice(path.iterdir(), limit + 1))
        if len(items) > limit:
            problems.append(f"truncated:{path.name}")
        return sorted(items[:limit])
    except OSError:
        problems.append(f"unavailable:{path.name}")
        return []


def discover_topology(
    *, sys_root: str | Path = "/sys", proc_root: str | Path = "/proc"
) -> dict[str, Any]:
    """Collect a visible PCI/NUMA/NIC graph without assuming runtime GPU access.

    Injectable roots permit fixture/replay tests. /proc/self/status provides the
    kernel's effective CPU and memory masks, including cpuset restrictions.
    """
    root, proc = Path(sys_root), Path(proc_root)
    report: dict[str, Any] = {
        "schema_version": 1,
        "report_type": "topology",
        "tool_version": __version__,
        "status": "INCONCLUSIVE",
        "scope": {
            "view": "visible_filesystem",
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "allowed_cpus": None,
            "allowed_memory_nodes": None,
            "status_meaning": "collection_completeness_not_hardware_health",
        },
        "data": {"nodes": [], "edges": []},
        "evidence": [],
        "limitations": [
            "PCI presence does not imply runtime access or compute support.",
            "Physical locality does not establish RDMA or peer-access capability.",
            "NVLink is not inferred from PCIe; use a vendor matrix separately.",
        ],
        "sources": [
            {"id": "linux-pci", "url": "https://docs.kernel.org/PCI/sysfs-pci.html"},
            {
                "id": "linux-proc",
                "url": "https://docs.kernel.org/filesystems/proc.html",
            },
        ],
    }
    if sys.platform != "linux" and root == Path("/sys"):
        report["limitations"].append("linux_required")
        return report
    nodes, edges = report["data"]["nodes"], report["data"]["edges"]
    problems: list[str] = []
    status = _read(proc / "self/status")
    if status is not None:
        fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
        report["scope"]["allowed_cpus"] = _ids(fields.get("Cpus_allowed_list"))
        report["scope"]["allowed_memory_nodes"] = _ids(fields.get("Mems_allowed_list"))
    if (
        report["scope"]["allowed_cpus"] is None
        or report["scope"]["allowed_memory_nodes"] is None
    ):
        problems.append("effective_process_masks_unavailable")
    report["evidence"].append({"id": "process-masks", "source": "proc/self/status"})

    for entry in _entries(root / "devices/system/node", 1024, problems):
        if re.fullmatch(r"node\d+", entry.name):
            node_id = int(entry.name[4:])
            nodes.append(
                {
                    "id": f"numa:{node_id}",
                    "kind": "numa",
                    "numa_node": node_id,
                    "cpu_ids": _ids(_read(entry / "cpulist")),
                    "evidence_id": f"numa:{node_id}",
                }
            )
            report["evidence"].append(
                {
                    "id": f"numa:{node_id}",
                    "source": f"sys/devices/system/node/{entry.name}",
                }
            )

    pci_entries = _entries(root / "bus/pci/devices", 4096, problems)
    pci_ids = {
        entry.name.lower() for entry in pci_entries if _BDF.fullmatch(entry.name)
    }
    numa_ids = {n["numa_node"] for n in nodes}
    for entry in pci_entries:
        address = entry.name.lower()
        if address not in pci_ids:
            continue
        device_id = f"pci:{address}"
        numa = _number(_read(entry / "numa_node"))
        numa = numa if numa is not None and numa >= 0 else None
        class_code = _number(_read(entry / "class"), 16)
        major = (class_code >> 16) if class_code is not None else None
        node = {
            "id": device_id,
            "kind": "accelerator_candidate" if major in {3, 18} else "pci_device",
            "pci_address": address,
            "class_code": class_code,
            "vendor_id": _read(entry / "vendor"),
            "device_id": _read(entry / "device"),
            "numa_node": numa,
            "local_cpus": _ids(_read(entry / "local_cpulist")),
            "current_link_speed": _read(entry / "current_link_speed"),
            "current_link_width": _number(_read(entry / "current_link_width")),
            "evidence_id": device_id,
        }
        nodes.append(node)
        report["evidence"].append(
            {"id": device_id, "source": f"sys/bus/pci/devices/{address}"}
        )
        if numa in numa_ids:
            edges.append(
                {
                    "source": device_id,
                    "target": f"numa:{numa}",
                    "kind": "numa_locality",
                    "evidence_id": device_id,
                }
            )
        try:
            for parent in entry.resolve(strict=True).parents:
                if parent.name.lower() in pci_ids:
                    edges.append(
                        {
                            "source": device_id,
                            "target": f"pci:{parent.name.lower()}",
                            "kind": "pci_parent",
                            "evidence_id": device_id,
                        }
                    )
                    break
        except (OSError, RuntimeError):
            problems.append(f"unresolved:{address}")

    for category, kind in (("net", "nic"), ("infiniband", "rdma_interface")):
        for entry in _entries(root / "class" / category, 1024, problems):
            node_id = f"{kind}:{entry.name}"
            try:
                address = (entry / "device").resolve(strict=True).name.lower()
            except (OSError, RuntimeError):
                address = None
            nodes.append(
                {
                    "id": node_id,
                    "kind": kind,
                    "name": entry.name,
                    "pci_address": address if address in pci_ids else None,
                    "evidence_id": node_id,
                }
            )
            report["evidence"].append(
                {"id": node_id, "source": f"sys/class/{category}/{entry.name}"}
            )
            if address in pci_ids:
                edges.append(
                    {
                        "source": node_id,
                        "target": f"pci:{address}",
                        "kind": "pci_identity",
                        "evidence_id": node_id,
                    }
                )
    report["limitations"].extend(sorted(set(problems)))
    report["status"] = "WARN" if problems else "PASS"
    if not pci_ids:
        report["status"] = "INCONCLUSIVE"
    return report


def recommend_affinity(report: dict[str, Any], device_id: str) -> dict[str, Any]:
    """Suggest only a permitted local CPU/memory set; never change affinity."""
    if (
        not isinstance(report, dict)
        or report.get("report_type") != "topology"
        or report.get("schema_version") != 1
    ):
        raise ValueError("Expected a version 1 topology report")
    if not isinstance(report.get("data"), dict) or not isinstance(
        report.get("scope"), dict
    ):
        raise ValueError("Topology requires data and scope objects")
    nodes = report["data"].get("nodes")
    if not isinstance(nodes, list) or any(not isinstance(n, dict) for n in nodes):
        raise ValueError("Topology requires a node list")
    devices = [n for n in nodes if n.get("id") == device_id]
    if len(devices) != 1:
        raise ValueError("Device ID is absent or ambiguous")
    device = devices[0]
    numa = device.get("numa_node")
    scope = report.get("scope", {})
    result: dict[str, Any] = {
        "device_id": device_id,
        "status": "INCONCLUSIVE",
        "cpu_ids": [],
        "memory_nodes": [],
        "reasons": [],
        "applied": False,
    }
    local = device.get("local_cpus")
    numa_nodes = [
        n for n in nodes if n.get("kind") == "numa" and n.get("numa_node") == numa
    ]
    if local is None and len(numa_nodes) == 1:
        local = numa_nodes[0].get("cpu_ids")
    allowed, memory = scope.get("allowed_cpus"), scope.get("allowed_memory_nodes")
    masks = (local, allowed, memory)
    if (
        type(numa) is not int
        or numa < 0
        or any(not isinstance(m, list) for m in masks)
        or any(type(x) is not int or x < 0 for m in masks for x in m)
    ):
        result["reasons"].append("locality_or_effective_masks_unknown")
        return result
    cpus = sorted(set(local) & set(allowed))
    if not cpus or numa not in memory:
        result["status"] = "WARN"
        result["reasons"].append("no_permitted_local_cpu_and_memory_combination")
        return result
    result.update(status="PASS", cpu_ids=cpus, memory_nodes=[numa])
    result["reasons"].append("locality_intersected_with_effective_process_masks")
    return result


def parse_nvidia_matrix(text: str) -> dict[str, Any]:
    return parse_vendor_matrix(text, vendor="nvidia")


def parse_vendor_matrix(text: str, *, vendor: str) -> dict[str, Any]:
    """Import nvidia-smi topo -m path labels, without guessing PCI identities.

    GPU/NIC aliases remain scoped to this one text snapshot. NV# records a bonded
    link count, not measured bandwidth or a proven direct point-to-point link.
    """
    if not isinstance(text, str) or len(text.encode()) > 1_048_576:
        raise ValueError("Topology matrix exceeds 1 MiB or is not text")
    if vendor not in {"nvidia", "alibaba"}:
        raise ValueError("Unsupported topology vendor")
    prefix, bond = ("GPU", "NV") if vendor == "nvidia" else ("PPU", "ICN")
    alias_pattern = rf"(?:{prefix}|NIC)\d+"
    labels: list[str] = []
    rows: dict[str, list[str]] = {}
    for line in text.splitlines():
        words = line.split()
        if not words or words[0].startswith("Legend"):
            continue
        if not labels and re.fullmatch(alias_pattern, words[0]):
            for word in words:
                if not re.fullmatch(alias_pattern, word):
                    break
                labels.append(word)
            if len(set(labels)) != len(labels) or len(labels) > 256:
                raise ValueError("Invalid matrix header")
            continue
        if labels and words[0] in labels:
            if words[0] in rows or len(words) < len(labels) + 1:
                raise ValueError("Duplicate or incomplete matrix row")
            values = words[1 : len(labels) + 1]
            if any(
                not re.fullmatch(rf"X|SYS|NODE|PHB|PXB|PIX|{bond}[1-9]\d*", x)
                for x in values
            ):
                raise ValueError("Unrecognized matrix path label")
            rows[words[0]] = values
    if not labels or set(rows) != set(labels):
        raise ValueError("Incomplete nvidia-smi topology matrix")
    edges = []
    for i, source in enumerate(labels):
        if rows[source][i] != "X":
            raise ValueError("Invalid matrix diagonal")
        for j in range(i + 1, len(labels)):
            label = rows[source][j]
            if label != rows[labels[j]][i] or label == "X":
                raise ValueError("Inconsistent matrix connectivity")
            edges.append(
                {
                    "source": source,
                    "target": labels[j],
                    "path_label": label,
                    ("nvlink_bond_count" if vendor == "nvidia" else "icn_bond_count"): (
                        int(label[len(bond) :]) if label.startswith(bond) else None
                    ),
                }
            )
    return {
        "aliases": labels,
        "edges": edges,
        "identity_scope": "provided_matrix_only",
        "source_url": (
            "https://docs.nvidia.com/deploy/nvidia-smi/index.html#topology"
            if vendor == "nvidia"
            else "https://developer.t-head.cn/docs_center/doc_detail/index.html?projectId=39&chapterId=221"
        ),
    }
