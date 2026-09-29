"""Independent CPU array simulation exercises workload correctness branches."""

from __future__ import annotations

import sys
from array import array
from types import SimpleNamespace

from omnismi.probe_worker import execute


class Tensor:
    corrupt_copy = False

    def __init__(self, size):
        self.size = size
        count = size[0] * size[1] if isinstance(size, tuple) else size
        self.values = array("f", [0]) * count

    def fill_(self, value):
        self.values = array("f", [value]) * len(self.values)
        return self

    def copy_(self, source):
        self.values = array("f", source.values)
        if self.corrupt_copy:
            self.values[0] += 1
        return self


def fake_torch(monkeypatch):
    def empty(size, **kwargs):
        return Tensor(size)

    def add(a, b, *, out):
        out.values = array("f", (x + y for x, y in zip(a.values, b.values)))

    def mm(a, b, *, out=None):
        # Test reference supports constant matrices, independently checking sum.
        value = sum(a.values[k] * b.values[k * b.size[1]] for k in range(a.size[1]))
        return (out if out is not None else Tensor((a.size[0], b.size[1]))).fill_(value)

    runtime = SimpleNamespace(
        is_available=lambda: True,
        device_count=lambda: 1,
        set_device=lambda i: None,
        synchronize=lambda i: None,
        get_device_properties=lambda i: SimpleNamespace(
            name="fixture", uuid="GPU-fixture"
        ),
    )
    torch = SimpleNamespace(
        cuda=runtime,
        version=SimpleNamespace(hip=None),
        __version__="test",
        empty=empty,
        empty_like=lambda x: Tensor(x.size),
        float32="fp32",
        add=add,
        mm=mm,
        equal=lambda a, b: a.values == b.values,
        ones=lambda size, **kw: Tensor(size).fill_(1),
        ones_like=lambda x: Tensor(x.size).fill_(1),
        full_like=lambda x, v: Tensor(x.size).fill_(v),
    )
    monkeypatch.setitem(sys.modules, "torch", torch)


def test_memory_compute_patterns_and_corruption(monkeypatch):
    fake_torch(monkeypatch)
    config = dict(
        mode="self-test",
        vendor="nvidia",
        device=0,
        memory_mib=1,
        repeats=2,
        pattern="copy",
    )
    report = execute(config)
    assert report["status"] == "PASS"
    assert len(report["checks"]) == 9
    assert all(check["passed"] for check in report["checks"])
    monkeypatch.setattr(Tensor, "corrupt_copy", True)
    report = execute(config)
    assert report["status"] == "FAIL" and report["reason"] == "data_mismatch"
    assert not report["hardware_fault_confirmed"]


def test_bandwidth_byte_accounting_and_vendor_mismatch(monkeypatch):
    fake_torch(monkeypatch)
    config = dict(
        mode="bandwidth",
        vendor="nvidia",
        device=0,
        memory_mib=1,
        repeats=2,
        pattern="triad",
    )
    report = execute(config)
    assert report["status"] == "PASS"
    sample = report["samples"][0]
    assert (
        sample["bytes_per_iteration"]
        == report["measurement"]["signature"]["buffer_bytes"] * 3
    )
    assert sample["value"] == sample["bytes_per_iteration"] * 20 / sample["seconds"]
    config["vendor"] = "amd"
    assert execute(config)["reason"] == "runtime_vendor_mismatch"


def test_compute_throughput_uses_dense_flops_and_matching_probe_identity(monkeypatch):
    fake_torch(monkeypatch)
    report = execute(
        dict(
            mode="compute",
            vendor="nvidia",
            device=0,
            memory_mib=1,
            repeats=2,
            pattern="copy",
        )
    )
    assert report["status"] == "PASS"
    assert report["measurement"]["metric"] == "compute_throughput"
    assert report["measurement"]["unit"] == "FLOP/s"
    assert report["measurement"]["signature"]["byte_convention"] == "dense_2mnk"
    assert report["samples"][0]["flops_per_iteration"] == 2 * 256**3


def test_corruption_only_in_timed_workload_cannot_produce_measurement(monkeypatch):
    fake_torch(monkeypatch)
    torch = sys.modules["torch"]
    add = torch.add
    calls = 0

    def corrupt_after_preflight(a, b, *, out):
        nonlocal calls
        calls += 1
        add(a, b, out=out)
        if calls > 4:
            out.values[0] += 1

    torch.add = corrupt_after_preflight
    report = execute(
        dict(
            mode="bandwidth",
            vendor="nvidia",
            device=0,
            memory_mib=1,
            repeats=2,
            pattern="triad",
        )
    )
    assert report["status"] == "FAIL"
    assert report["reason"] == "timed_result_data_mismatch"
    assert "measurement" not in report
