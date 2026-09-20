"""Tests for CUDA_VISIBLE_DEVICES filtering."""

from __future__ import annotations

from omnismi.visibility import filter_gpus_by_visibility, parse_cuda_visible_devices


class FakeInfo:
    def __init__(self, uuid=None):
        self.uuid = uuid


class FakeGPU:
    def __init__(self, index, uuid=None):
        self.index = index
        self._uuid = uuid

    def info(self):
        return FakeInfo(self._uuid)


def test_parse_unset():
    assert parse_cuda_visible_devices("0,1") == ["0", "1"]
    assert parse_cuda_visible_devices("") == []


def test_filter_by_index(monkeypatch):
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    devices = [FakeGPU(0), FakeGPU(1), FakeGPU(2)]
    selected, ctx = filter_gpus_by_visibility(
        devices, visible_only=True, cuda_visible_devices="1,0"
    )
    assert [d.index for d in selected] == [1, 0]
    assert ctx.physical_indices == [1, 0]
    assert ctx.logical_indices == [0, 1]


def test_filter_empty_means_none(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    devices = [FakeGPU(0), FakeGPU(1)]
    selected, ctx = filter_gpus_by_visibility(devices, visible_only=True)
    assert selected == []
    assert ctx.physical_indices == []


def test_filter_all_devices_ignores_cvd(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    devices = [FakeGPU(0), FakeGPU(1)]
    selected, ctx = filter_gpus_by_visibility(devices, visible_only=False)
    assert len(selected) == 2
    assert ctx.mode == "all"


def test_filter_by_uuid(monkeypatch):
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    devices = [
        FakeGPU(0, uuid="GPU-aaa"),
        FakeGPU(1, uuid="GPU-bbb"),
    ]
    selected, _ = filter_gpus_by_visibility(
        devices, visible_only=True, cuda_visible_devices="GPU-bbb"
    )
    assert [d.index for d in selected] == [1]
