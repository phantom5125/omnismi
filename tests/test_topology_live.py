"""Stable identity, link semantics and failure atomicity of live collectors."""

from __future__ import annotations

import copy

import pytest

from omnismi import topology_live as live
from omnismi.topology import parse_vendor_matrix

IDENTITIES = (
    "index, uuid, pci.bus_id\n0, GPU-a, 00000000:41:00.0\n1, GPU-b, 0000:42:00.0\n"
)
MATRIX = """GPU0 GPU1 NIC0 CPU Affinity NUMA Affinity
GPU0 X NV4 PIX 0-3 0
GPU1 NV4 X PHB 0-3 0
NIC0 PIX PHB X
Legend:
NIC Legend:
NIC0: mlx5_0
"""
LISTING = """GPU 0: Test (UUID: GPU-a)
  MIG 1g.5gb Device 0: (UUID: MIG-a)
GPU 1: Test (UUID: GPU-b)
"""


def graph():
    return {
        "schema_version": 1,
        "report_type": "topology",
        "status": "PASS",
        "data": {
            "nodes": [
                {
                    "id": "rdma_interface:mlx5_0",
                    "kind": "rdma_interface",
                    "name": "mlx5_0",
                }
            ],
            "edges": [],
        },
        "scope": {},
        "evidence": [],
        "sources": [],
        "limitations": [],
    }


def responses(monkeypatch, outputs):
    calls = []
    monkeypatch.setattr(live.shutil, "which", lambda name: "/test/" + name)

    def query(args, **kwargs):
        calls.append(args)
        assert 0 < kwargs["timeout"] <= 15
        return outputs.pop(0)

    monkeypatch.setattr(live, "query_text", query)
    return calls


def test_live_identity_links_nic_and_mig(monkeypatch):
    calls = responses(monkeypatch, [IDENTITIES, MATRIX, LISTING, IDENTITIES])
    report = live.collect_vendor_topology(graph(), "nvidia")
    assert len(calls) == 4
    assert report["data"]["vendor_collections"][0]["status"] == "ok"
    assert any(
        edge["source"] == "pci:0000:41:00.0" and edge.get("nvlink_bond_count") == 4
        for edge in report["data"]["edges"]
    )
    assert any(
        edge["target"] == "rdma_interface:mlx5_0" for edge in report["data"]["edges"]
    )
    assert any(node["id"] == "uuid:MIG-a" for node in report["data"]["nodes"])


@pytest.mark.parametrize("case", ["identity_change", "duplicate_nic", "asymmetric"])
def test_failed_join_does_not_mutate_graph(monkeypatch, case):
    matrix = MATRIX
    after = IDENTITIES
    if case == "identity_change":
        after = after.replace("GPU-a", "GPU-new")
    elif case == "duplicate_nic":
        matrix += "NIC0: mlx5_1\n"
    else:
        matrix = matrix.replace("GPU1 NV4", "GPU1 SYS")
    responses(monkeypatch, [IDENTITIES, matrix, LISTING, after])
    report = graph()
    before = copy.deepcopy(report["data"])
    live.collect_vendor_topology(report, "nvidia")
    assert report["status"] == "WARN"
    assert report["data"]["nodes"] == before["nodes"]
    assert report["data"]["edges"] == before["edges"]


def test_ppu_icn_does_not_become_nvlink(monkeypatch):
    identities = IDENTITIES.replace("GPU-", "PPU-")
    matrix = MATRIX.replace("GPU", "PPU").replace("NV4", "ICN2")
    responses(monkeypatch, [identities, matrix, identities])
    report = live.collect_vendor_topology(graph(), "alibaba")
    edge = report["data"]["edges"][0]
    assert edge["icn_bond_count"] == 2 and "nvlink_bond_count" not in edge
    with pytest.raises(ValueError):
        parse_vendor_matrix(matrix.replace("ICN2", "NV4"), vendor="alibaba")


def test_missing_tool_and_invalid_identity(monkeypatch):
    monkeypatch.setattr(live.shutil, "which", lambda _: None)
    report = live.collect_vendor_topology(graph(), "nvidia")
    assert report["data"]["vendor_collections"][0]["status"] == "unavailable"
    with pytest.raises(ValueError):
        live.parse_identities(IDENTITIES.replace("42:00.0", "41:00.0"), prefix="GPU")
