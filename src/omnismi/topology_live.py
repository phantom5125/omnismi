"""Bounded vendor snapshots joined by PCI identity, never ordinal alone."""

from __future__ import annotations

import csv
import io
import re
import shutil
import time
from copy import deepcopy
from typing import Any

from omnismi.backends.command import query_text
from omnismi.errors import BackendError
from omnismi.identity import normalize_bdf
from omnismi.topology import parse_vendor_matrix


def parse_identities(text: str, *, prefix: str) -> dict[str, dict[str, str]]:
    reader = csv.reader(io.StringIO(text), skipinitialspace=True, strict=True)
    try:
        rows = list(reader)
    except csv.Error as exc:
        raise ValueError("Malformed identity CSV") from exc
    if not rows or [x.strip() for x in rows[0]] != ["index", "uuid", "pci.bus_id"]:
        raise ValueError("Unknown identity query header")
    result, uuids, addresses = {}, set(), set()
    for row in rows[1:]:
        if not row:
            continue
        if len(row) != 3:
            raise ValueError("Malformed identity row")
        index, uuid, address = [x.strip() for x in row]
        if not index.isdecimal() or not uuid or uuid.lower() == "n/a":
            raise ValueError("Incomplete device identity")
        address = normalize_bdf(address)
        alias = f"{prefix}{int(index)}"
        if alias in result or uuid in uuids or address in addresses:
            raise ValueError("Ambiguous identity snapshot")
        uuids.add(uuid)
        addresses.add(address)
        result[alias] = {"uuid": uuid, "pci_address": address}
    return result


def parse_mig(text: str, identities: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    children, seen, parent = [], set(), None
    for line in text.splitlines():
        gpu = re.fullmatch(r"GPU (\d+): .+ \(UUID: ([^()\s]+)\)", line)
        if gpu:
            parent = identities.get(f"GPU{int(gpu[1])}")
            if parent is None or parent["uuid"] != gpu[2]:
                raise ValueError("MIG parent identity changed")
            continue
        mig = re.fullmatch(r"\s+MIG (.+) Device (\d+): \(UUID: ([^()\s]+)\)", line)
        if mig:
            if parent is None or mig[3] in seen:
                raise ValueError("Ambiguous MIG identity")
            seen.add(mig[3])
            children.append(
                {
                    "id": f"uuid:{mig[3]}",
                    "kind": "accelerator_partition",
                    "uuid": mig[3],
                    "profile": mig[1],
                    "parent_uuid": parent["uuid"],
                    "parent_pci_address": parent["pci_address"],
                    "evidence_id": "nvidia-mig-list",
                }
            )
        elif line.strip():
            raise ValueError("Unrecognized nvidia-smi device list")
    return children


def collect_vendor_topology(
    report: dict[str, Any], vendor: str, *, timeout: float = 15.0
) -> dict[str, Any]:
    """Augment a graph with before/after-checked management identities."""
    if vendor not in {"nvidia", "alibaba"} or not 0 < timeout <= 60:
        raise ValueError("Unsupported topology vendor or timeout")
    tool, prefix, flag = (
        ("nvidia-smi", "GPU", "gpu")
        if vendor == "nvidia"
        else ("ppu-smi", "PPU", "ppu")
    )
    collection = {"vendor": vendor, "status": "unavailable", "reason": "tool_not_found"}
    report["data"].setdefault("vendor_collections", []).append(collection)
    executable = shutil.which(tool)
    if not executable:
        if report["status"] == "PASS":
            report["status"] = "WARN"
        return report
    deadline = time.monotonic() + timeout

    def query(args: list[str]) -> str:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise BackendError("Topology deadline exceeded")
        return query_text([executable, *args], timeout=remaining)

    try:
        identity_args = [
            f"--query-{flag}=index,uuid,pci.bus_id",
            "--format=csv,nounits",
        ]
        before = parse_identities(query(identity_args), prefix=prefix)
        text = query(["topo", "-m"])
        matrix = parse_vendor_matrix(text, vendor=vendor)
        partitions = []
        # Optional MIG listing must not discard an otherwise usable physical graph.
        mig_error = None
        if vendor == "nvidia":
            try:
                partitions = parse_mig(query(["-L"]), before)
            except (ValueError, BackendError) as exc:
                mig_error = str(exc)
        after = parse_identities(query(identity_args), prefix=prefix)
        if before != after:
            raise ValueError("Device identity changed during topology collection")
        nodes, edges = deepcopy(report["data"]["nodes"]), deepcopy(
            report["data"]["edges"]
        )
        known = {node["id"]: node for node in nodes}
        mapping = {}
        for alias, identity in before.items():
            node_id = f"pci:{identity['pci_address']}"
            mapping[alias] = node_id
            if node_id not in known:
                node = {
                    "id": node_id,
                    "kind": "accelerator",
                    **identity,
                    "vendor": vendor,
                    "numa_node": None,
                    "local_cpus": None,
                    "evidence_id": f"{vendor}-identities",
                }
                nodes.append(node)
                known[node_id] = node
            else:
                known[node_id].update(
                    uuid=identity["uuid"], vendor=vendor, kind="accelerator"
                )
        nic_aliases = {}
        for alias, name in re.findall(r"^\s*(NIC\d+):\s*([^\s]+)\s*$", text, re.M):
            if alias in nic_aliases:
                raise ValueError("Duplicate NIC alias")
            nic_aliases[alias] = name
        for alias, name in nic_aliases.items():
            matches = [
                node["id"]
                for node in nodes
                if node.get("kind") == "rdma_interface" and node.get("name") == name
            ]
            if len(matches) == 1:
                mapping[alias] = matches[0]
        unresolved_aliases = sorted(set(matrix["aliases"]) - set(mapping))
        unresolved = []
        for edge in matrix["edges"]:
            source, target = mapping.get(edge["source"]), mapping.get(edge["target"])
            if source and target:
                edges.append(
                    {
                        **edge,
                        "source": source,
                        "target": target,
                        "kind": "vendor_path",
                        "vendor": vendor,
                        "evidence_id": f"{vendor}-matrix",
                    }
                )
            else:
                unresolved.append(edge)
        for node in partitions:
            nodes.append(node)
            edges.append(
                {
                    "source": node["id"],
                    "target": f"pci:{node['parent_pci_address']}",
                    "kind": "partition_parent",
                    "evidence_id": "nvidia-mig-list",
                }
            )
        report["data"].update(nodes=nodes, edges=edges)
        report["evidence"].extend(
            [
                {
                    "id": f"{vendor}-identities",
                    "source": f"{tool} identity CSV before/after",
                },
                {"id": f"{vendor}-matrix", "source": f"{tool} topo -m"},
            ]
        )
        if partitions:
            report["evidence"].append(
                {"id": "nvidia-mig-list", "source": "nvidia-smi -L"}
            )
        report["sources"].append(
            {"id": f"{vendor}-topology", "url": matrix["source_url"]}
        )
        collection.update(
            status="partial" if unresolved or unresolved_aliases or mig_error else "ok",
            reason=mig_error,
            unresolved_edges=unresolved,
            unresolved_aliases=unresolved_aliases,
            alias_map=mapping,
        )
        report["limitations"].append(
            "Identity snapshots bracket collection but are not atomic. "
            "Matrix paths do not prove peer access."
        )
    except (OSError, ValueError, BackendError) as exc:
        collection.update(status="error", reason=str(exc))
    if collection["status"] != "ok" and report["status"] == "PASS":
        report["status"] = "WARN"
    return report
