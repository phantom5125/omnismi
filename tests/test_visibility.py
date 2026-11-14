"""Tests for CUDA_VISIBLE_DEVICES filtering."""

from __future__ import annotations

import pytest

from omnismi.visibility import filter_gpus_by_visibility, parse_cuda_visible_devices


class FakeInfo:
    def __init__(self, uuid=None, vendor="nvidia"):
        self.uuid = uuid
        self.vendor = vendor


class FakeGPU:
    def __init__(self, index, uuid=None, vendor="nvidia"):
        self.index = index
        self._uuid = uuid
        self._vendor = vendor

    def info(self):
        return FakeInfo(self._uuid, self._vendor)


@pytest.fixture(autouse=True)
def clear_visibility_environment(monkeypatch):
    for name in (
        "CUDA_VISIBLE_DEVICES",
        "ROCR_VISIBLE_DEVICES",
        "HIP_VISIBLE_DEVICES",
        "GPU_DEVICE_ORDINAL",
    ):
        monkeypatch.delenv(name, raising=False)


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


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("GPU-aaab", [1]),
        ("gpu-AAAB", [1]),
        ("GPU-b", [2]),
        ("GPU-aaa", []),
        ("GPU-", []),
        ("aaab", []),
        ("ab", []),
        ("b", []),
        ("missing", []),
    ],
)
def test_uuid_selection_requires_unique_identity(token, expected):
    devices = [
        FakeGPU(0, uuid="GPU-aaaa"),
        FakeGPU(1, uuid="GPU-aaab"),
        FakeGPU(2, uuid="GPU-bbbb"),
        FakeGPU(3),
    ]
    selected, ctx = filter_gpus_by_visibility(devices, cuda_visible_devices=token)
    assert [device.index for device in selected] == expected
    assert ctx.physical_indices == expected
    assert ctx.logical_indices == list(range(len(expected)))


@pytest.mark.parametrize(
    "invalid_token", ["-1", "99", "GPU-unknown", "GPU-a", "", "0", "GPU-aaaa"]
)
def test_invalid_or_duplicate_identifier_stops_visibility(invalid_token):
    devices = [FakeGPU(0, "GPU-aaaa"), FakeGPU(1, "GPU-aaab"), FakeGPU(2, "GPU-bbbb")]
    selected, ctx = filter_gpus_by_visibility(
        devices, cuda_visible_devices=f"0,{invalid_token},2"
    )
    assert [device.index for device in selected] == [0]
    assert ctx.physical_indices == [0]
    assert ctx.logical_indices == [0]


def test_cuda_visibility_does_not_filter_amd_devices():
    devices = [
        FakeGPU(0, vendor="nvidia"),
        FakeGPU(1, vendor="nvidia"),
        FakeGPU(2, vendor="amd"),
    ]

    selected, ctx = filter_gpus_by_visibility(devices, cuda_visible_devices="1")

    assert [device.index for device in selected] == [1, 2]
    assert ctx.physical_indices == [1, 2]
    assert ctx.logical_indices == [0, 1]
    assert ctx.enforcement == "runtime_hint_only"


def test_empty_rocr_visibility_hides_only_amd_devices(monkeypatch):
    devices = [FakeGPU(0), FakeGPU(1, vendor="amd")]
    monkeypatch.setenv("ROCR_VISIBLE_DEVICES", "")

    selected, ctx = filter_gpus_by_visibility(devices)

    assert [device.index for device in selected] == [0]
    assert ctx.env == {"ROCR_VISIBLE_DEVICES": ""}


def test_rocr_visibility_supports_unique_uuid_prefix(monkeypatch):
    devices = [
        FakeGPU(0, "GPU-aaaa", "amd"),
        FakeGPU(1, "GPU-bbbb", "amd"),
    ]
    monkeypatch.setenv("ROCR_VISIBLE_DEVICES", "GPU-b")

    selected, ctx = filter_gpus_by_visibility(devices)

    assert [device.index for device in selected] == [1]
    assert ctx.logical_indices == [0]


def test_multiple_amd_controls_are_intersected_and_reported(monkeypatch):
    devices = [
        FakeGPU(0, vendor="amd"),
        FakeGPU(1, vendor="amd"),
        FakeGPU(2, vendor="amd"),
    ]
    monkeypatch.setenv("ROCR_VISIBLE_DEVICES", "0,1")
    monkeypatch.setenv("HIP_VISIBLE_DEVICES", "1,2")

    selected, ctx = filter_gpus_by_visibility(devices)

    assert [device.index for device in selected] == [1]
    assert ctx.env == {
        "ROCR_VISIBLE_DEVICES": "0,1",
        "HIP_VISIBLE_DEVICES": "1,2",
    }
    assert "intersected" in ctx.warnings[0]
