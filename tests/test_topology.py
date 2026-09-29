"""Filesystem topology replay and affinity constraints without accelerator hardware."""

from __future__ import annotations

import json

import pytest

from omnismi.cli import main
from omnismi.topology import (
    discover_topology,
    parse_cpu_list,
    parse_nvidia_matrix,
    recommend_affinity,
)


@pytest.fixture
def filesystem(tmp_path):
    root, proc = tmp_path / "sys", tmp_path / "proc"

    def put(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    put(proc / "self/status", "Cpus_allowed_list:\t2-3,10\nMems_allowed_list:\t0\n")
    put(root / "devices/system/node/node0/cpulist", "0-3,8-11")
    put(root / "devices/system/node/node1/cpulist", "4-7,12-15")
    bridge = root / "devices/pci0000:00/0000:00:01.0"
    gpu = bridge / "0000:41:00.0"
    nic = bridge / "0000:42:00.0"
    for path, class_code in (
        (bridge, "0x060400"),
        (gpu, "0x030200"),
        (nic, "0x020000"),
    ):
        put(path / "class", class_code)
        put(path / "numa_node", "0")
        put(path / "local_cpulist", "0-3,8-11")
        put(path / "vendor", "0x1234")
        put(path / "device", "0xabcd")
        put(path / "current_link_speed", "16.0 GT/s PCIe")
        put(path / "current_link_width", "16")
        link = root / "bus/pci/devices" / path.name
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(path, target_is_directory=True)
    for kind, name in (("net", "eth0"), ("infiniband", "mlx5_0")):
        entry = root / "class" / kind / name
        entry.mkdir(parents=True)
        (entry / "device").symlink_to(nic, target_is_directory=True)
    return root, proc


def test_graph_has_pci_parent_numa_and_nic_identities(filesystem):
    root, proc = filesystem
    report = discover_topology(sys_root=root, proc_root=proc)
    assert report["status"] == "PASS"
    edges = report["data"]["edges"]
    assert any(
        e["source"] == "pci:0000:41:00.0"
        and e["target"] == "pci:0000:00:01.0"
        and e["kind"] == "pci_parent"
        for e in edges
    )
    assert any(
        e["source"] == "nic:eth0" and e["target"] == "pci:0000:42:00.0" for e in edges
    )
    assert any(e["source"] == "rdma_interface:mlx5_0" for e in edges)
    assert not any("nvlink" in e["kind"] for e in edges)


def test_affinity_intersects_sparse_effective_cpu_and_memory_masks(filesystem):
    report = discover_topology(sys_root=filesystem[0], proc_root=filesystem[1])
    result = recommend_affinity(report, "pci:0000:41:00.0")
    assert result["status"] == "PASS"
    assert result["cpu_ids"] == [2, 3, 10]
    assert result["memory_nodes"] == [0]
    assert not result["applied"]
    report["scope"]["allowed_memory_nodes"] = [1]
    result = recommend_affinity(report, "pci:0000:41:00.0")
    assert result["status"] == "WARN" and not result["cpu_ids"]
    report["scope"]["allowed_memory_nodes"] = [0]
    report["scope"]["allowed_cpus"] = []
    assert recommend_affinity(report, "pci:0000:41:00.0")["status"] == "WARN"


def test_unknown_numa_and_unreadable_masks_do_not_guess(filesystem):
    root, proc = filesystem
    (root / "bus/pci/devices/0000:41:00.0/numa_node").write_text("-1")
    report = discover_topology(sys_root=root, proc_root=proc)
    assert recommend_affinity(report, "pci:0000:41:00.0")["status"] == "INCONCLUSIVE"
    (proc / "self/status").unlink()
    report = discover_topology(sys_root=root, proc_root=proc)
    assert report["status"] == "WARN"
    assert report["scope"]["allowed_cpus"] is None


@pytest.mark.parametrize(
    "value", ["-1", "1-0", "1,,2", "0-99999999", "1-3:2", "garbage"]
)
def test_invalid_masks_are_bounded(value):
    with pytest.raises(ValueError):
        parse_cpu_list(value)


def test_cpu_list_is_sparse_and_stable():
    assert parse_cpu_list("0-2,8,10-11,1") == [0, 1, 2, 8, 10, 11]
    assert parse_cpu_list("") == []


def test_nvlink_matrix_preserves_tool_alias_scope():
    matrix = """GPU0 GPU1 NIC0 CPU Affinity NUMA Affinity
GPU0 X NV4 PIX 0-7 0
GPU1 NV4 X PHB 0-7 0
NIC0 PIX PHB X
Legend:
X = Self
"""
    result = parse_nvidia_matrix(matrix)
    assert result["edges"][0]["nvlink_bond_count"] == 4
    assert result["identity_scope"] == "provided_matrix_only"
    assert "pci_address" not in result["edges"][0]
    with pytest.raises(ValueError, match="Inconsistent"):
        parse_nvidia_matrix(matrix.replace("GPU1 NV4", "GPU1 SYS"))
    with pytest.raises(ValueError, match="Unrecognized"):
        parse_nvidia_matrix(matrix.replace("NV4", "SOMETHING"))
    with pytest.raises(ValueError, match="Incomplete"):
        parse_nvidia_matrix("not a matrix")


def test_cli_replay_and_affinity(filesystem, tmp_path, capsys):
    report = discover_topology(sys_root=filesystem[0], proc_root=filesystem[1])
    path = tmp_path / "topology.json"
    path.write_text(json.dumps(report))
    assert (
        main(
            [
                "topology",
                "--input",
                str(path),
                "--recommend-affinity",
                "--device",
                "pci:0000:41:00.0",
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["data"]["affinity_recommendation"]["cpu_ids"] == [2, 3, 10]
    assert (
        main(["topology", "--input", str(path), "--device", "pci:0000:41:00.0"]) == 64
    )


def test_missing_filesystem_is_inconclusive(tmp_path):
    report = discover_topology(
        sys_root=tmp_path / "absent", proc_root=tmp_path / "absent"
    )
    assert report["status"] == "INCONCLUSIVE"
