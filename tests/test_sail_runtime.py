"""SAIL host protocol tests. CPU stand-ins do not certify HGGC or PPU hardware."""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest

from omnismi.probe_runtime import run_probe
from omnismi.sail_runtime import normalize


def config(mode="bandwidth", pattern="copy"):
    return dict(
        mode=mode, pattern=pattern, vendor="alibaba", device=1, memory_mib=1, repeats=2
    )


@pytest.fixture(scope="module")
def host_probe(tmp_path_factory):
    compiler = shutil.which("c++")
    if not compiler:
        pytest.skip("C++ compiler unavailable for synthetic SAIL host test")
    root = tmp_path_factory.mktemp("sail-host")
    (root / "sail_probe_host.hpp").write_bytes(
        files("omnismi.backends").joinpath("sail_probe_host.hpp").read_bytes()
    )
    # Independent host runtime and CPU operations. Production kernel source is
    # never transformed or compiled as CUDA; real HGGC remains an external gate.
    (root / "host.cpp").write_text(r"""
#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <cstddef>
typedef int hggcError_t;
const int hggcSuccess = 0, hggcMemcpyHostToDevice = 1, hggcMemcpyDeviceToHost = 2;
struct hggcDeviceProp {
    char name[256] = "synthetic \"SAIL\" PPU";
    int pciDomainID = 0, pciBusID = 65, pciDeviceID = 0;
};
static int selected = -1;
int hggcGetDeviceCount(int *out) { *out = 2; return 0; }
int hggcSetDevice(int index) { selected = index; return 0; }
int hggcGetDeviceProperties(hggcDeviceProp *out, int index) {
    *out = hggcDeviceProp{}; return index == selected ? 0 : 1;
}
int hggcRuntimeGetVersion(int *out) { *out = 20101; return 0; }
int hggcDriverGetVersion(int *out) { *out = 20102; return 0; }
int hggcMalloc(void **out, size_t bytes) {
    *out = std::malloc(bytes); return *out ? 0 : 1;
}
int hggcFree(void *ptr) { std::free(ptr); return 0; }
int hggcMemcpy(void *to, const void *from, size_t bytes, int) {
    std::memcpy(to, from, bytes); return 0;
}
int hggcGetLastError() { return std::getenv("SAIL_TEST_ERROR") ? 1 : 0; }
int hggcDeviceSynchronize() { return 0; }
const char *hggcGetErrorString(int) { return "synthetic runtime failure"; }
void sail_copy(const float *a, float *out, size_t count) {
    static int calls = 0;
    ++calls;
    std::copy(a, a + count, out);
    if (std::getenv("SAIL_TEST_CORRUPT") ||
        (calls > 4 && std::getenv("SAIL_TEST_CORRUPT_TIMED"))) out[0] += 1;
}
void sail_add(const float *a, const float *b, float *out, size_t count) {
    std::transform(a, a + count, b, out, [](float x, float y) { return x + y; });
}
void sail_matmul(const float *a, const float *b, float *out, int n) {
    for (int row = 0; row < n; ++row)
        for (int col = 0; col < n; ++col) {
            float value = 0;
            for (int k = 0; k < n; ++k) value += a[row*n+k] * b[k*n+col];
            out[row*n+col] = value;
        }
}
#include "sail_probe_host.hpp"
""")
    executable = root / "synthetic-sail-probe"
    result = subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(root / "host.cpp"),
            "-o",
            str(executable),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return str(executable)


def invoke(executable, settings, extra_env=None):
    result = subprocess.run(
        [
            executable,
            "--run",
            settings["mode"],
            str(settings["device"]),
            str(settings["memory_mib"]),
            str(settings["repeats"]),
            settings["pattern"],
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, **(extra_env or {})},
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    "mode,pattern",
    [
        ("self-test", "copy"),
        ("bandwidth", "copy"),
        ("bandwidth", "triad"),
        ("compute", "copy"),
    ],
)
def test_compiled_host_control_and_accounting(host_probe, mode, pattern):
    settings = config(mode, pattern)
    raw = invoke(host_probe, settings)
    report = normalize(raw, settings)
    assert report["status"] == "PASS"
    assert report["identity"]["name"] == 'synthetic "SAIL" PPU'
    assert report["identity"]["runtime_device_index"] == 1
    assert len(report["checks"]) == 9
    assert not report["hardware_fault_confirmed"]
    assert report["tested_buffer_bytes"] * 3 <= 1024**2
    if mode == "self-test":
        assert "measurement" not in report
    else:
        sample = report["samples"][0]
        work = (
            2 * 256**3
            if mode == "compute"
            else (1024**2 // 12) * 4 * (2 if pattern == "copy" else 3)
        )
        assert sample["value"] == work * 20 / sample["seconds"]
        signature = report["measurement"]["signature"]
        assert signature["runtime"] == "sail-hggc"
        assert signature["driver_version"] == "20102"


@pytest.mark.parametrize("variable", ["SAIL_TEST_CORRUPT", "SAIL_TEST_CORRUPT_TIMED"])
def test_corruption_during_preflight_or_timing_is_not_pass(host_probe, variable):
    report = normalize(invoke(host_probe, config(), {variable: "1"}), config())
    assert report["status"] == "FAIL"
    assert report["reason"] == "data_mismatch"
    assert "measurement" not in report
    assert not report["hardware_fault_confirmed"]


def test_runtime_error_is_not_hardware_failure(host_probe):
    report = normalize(invoke(host_probe, config(), {"SAIL_TEST_ERROR": "1"}), config())
    assert report["status"] == "INCONCLUSIVE"
    assert report["reason"] == "SAIL_runtime_error"


@pytest.mark.parametrize(
    "key,value", [("memory_mib", 0), ("device", 2), ("repeats", 101)]
)
def test_native_binary_also_enforces_bounds(host_probe, key, value):
    settings = {**config(), key: value}
    assert invoke(host_probe, settings)["status"] == "INCONCLUSIVE"


def test_protocol_rejects_misleading_success(host_probe):
    raw = invoke(host_probe, config())
    mutations = [
        lambda p: p.update(status=[]),
        lambda p: p.update(probe_version="unrecognized"),
        lambda p: p.update(mode="compute"),
        lambda p: p.update(buffer_bytes=1),
        lambda p: p.update(seconds=[0, 1]),
        lambda p: p.update(seconds=[float("nan"), 1]),
        lambda p: p.update(seconds=[True, 1]),
        lambda p: p.update(seconds=[1]),
        lambda p: p.update(checks=[]),
        lambda p: p["checks"][0].update(passed=False),
        lambda p: p["identity"].update(runtime_device_index=0),
        lambda p: p["identity"].update(vendor="nvidia"),
    ]
    for mutate in mutations:
        altered = copy.deepcopy(raw)
        mutate(altered)
        with pytest.raises(ValueError):
            normalize(altered, config())


def test_ppu_dispatch_uses_native_runtime_without_torch(host_probe, monkeypatch):
    import omnismi.probe_runtime as runtime

    monkeypatch.setenv("OMNISMI_SAIL_PROBE", host_probe)
    monkeypatch.setattr(
        runtime, "query_text", lambda *a, **kw: pytest.fail("Torch worker must not run")
    )
    report = run_probe(
        mode="self-test", vendor="alibaba", device=1, memory_mib=1, repeats=2
    )
    assert report["status"] == "PASS"
    assert report["scope"]["current_hardware_health"] == "INCONCLUSIVE"
    monkeypatch.delenv("OMNISMI_SAIL_PROBE")
    monkeypatch.setattr("omnismi.sail_runtime.shutil.which", lambda *a: None)
    report = run_probe(mode="self-test", vendor="alibaba")
    assert report["status"] == "INCONCLUSIVE"
    assert report["data"]["reason"] == "SAIL_native_probe_not_installed"


def test_sdk_build_is_explicit_bounded_and_does_not_overwrite(tmp_path, monkeypatch):
    from omnismi.backends import sail_build

    monkeypatch.setattr(sail_build.sys, "platform", "linux")
    monkeypatch.setattr(sail_build.shutil, "which", lambda _: "/installed/sdk/bin/hgcc")
    calls = []

    def compile_probe(argv, *, timeout):
        calls.append((argv, timeout))
        assert Path(argv[-3]).with_name("sail_probe_host.hpp").is_file()
        Path(argv[-1]).write_bytes(b"synthetic compiler output")

    monkeypatch.setattr(sail_build, "query_text", compile_probe)
    destination = tmp_path / "probe with spaces"
    metadata = sail_build.build_probe(
        output=str(destination), architectures=("ppu_15",), timeout=17
    )
    assert metadata["architectures"] == ["ppu_15"]
    assert set(metadata["source_sha256"]) == set(sail_build.SOURCES)
    assert calls[0][1] == 17
    assert "--gpu-architecture=ppu_15" in calls[0][0]
    assert destination.stat().st_mode & 0o111
    with pytest.raises(ValueError, match="new file"):
        sail_build.build_probe(output=str(destination))
    assert len(calls) == 1
