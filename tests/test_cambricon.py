"""CNDEV protocol and compile boundary; the mock header is not a vendor ABI."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest

from omnismi.backends import cambricon as mlu
from omnismi.backends.cndev_build import build_probe
from omnismi.errors import BackendError


def snapshot():
    return {
        "schema_version": 1,
        "collector": "omnismi-cndev",
        "sdk_api": 6,
        "devices": [
            {
                "index": 0,
                "name": "MLU-fixture",
                "uuid": "MLU-a",
                "driver": "6.5.24",
                "memory_total_mib": 1024,
                "memory_used_mib": 32,
                "power_w": None,
                "core_clock_mhz": 800,
                "memory_clock_mhz": 1600,
                "temperature_c": 45,
                "utilization_percent": 25,
            }
        ],
    }


def test_backend_identity_normalization_and_no_sdk(monkeypatch):
    monkeypatch.delenv("OMNISMI_CNDEV_PROBE", raising=False)
    monkeypatch.setattr(mlu.shutil, "which", lambda _: None)
    backend = mlu.CambriconBackend()
    assert not backend.available() and backend._import_failed
    backend.close()
    monkeypatch.setenv("OMNISMI_CNDEV_PROBE", "/test/collector")
    monkeypatch.setattr(mlu, "query_text", lambda args: json.dumps(snapshot()))
    assert backend.devices() == ["MLU-a"]
    assert backend.info("MLU-a", 2).vendor == "cambricon"
    metric = backend.metrics("MLU-a", 2)
    assert metric.memory_total_bytes == 1024**3
    assert metric.memory_used_bytes == 32 * 1024**2
    assert metric.power_w is None and metric.utilization_percent == 25
    backend.close()
    changed = snapshot()
    changed["devices"][0]["uuid"] = "MLU-b"
    monkeypatch.setattr(mlu, "query_text", lambda args: json.dumps(changed))
    with pytest.raises(BackendError, match="no longer visible"):
        backend.info("MLU-a", 2)


@pytest.mark.parametrize(
    "field,value",
    [
        ("uuid", ""),
        ("index", True),
        ("utilization_percent", 101),
        ("power_w", float("nan")),
        ("memory_used_mib", 1025),
        ("memory_used_mib", -1),
    ],
)
def test_bad_metric_and_identity_rejected(field, value):
    data = snapshot()
    data["devices"][0][field] = value
    with pytest.raises(BackendError):
        mlu.parse_snapshot(json.dumps(data))


@pytest.mark.skipif(
    not shutil.which("cc") or sys.platform not in {"linux", "darwin"},
    reason="C compiler required",
)
def test_sdk_compiled_bridge_protocol_and_error_values(tmp_path, monkeypatch):
    # Deliberately synthetic SDK: tests compiling with header-defined types and
    # the process protocol, not compatibility with any actual CNDEV installation.
    include, lib = tmp_path / "include", tmp_path / "lib"
    include.mkdir()
    lib.mkdir()
    declarations = {
        "cndevCardInfo_t": "int version; unsigned number;",
        "cndevUUID_t": "int version; char uuid[128];",
        "cndevVersionInfo_t": (
            "int version; unsigned driverMajorVersion,"
            "driverMinorVersion,driverBuildVersion;"
        ),
        "cndevMemoryInfoV2_t": "double globalMemory,physicalMemoryUsed;",
        "cndevDevicePowerInfo_t": "double usage;",
        "cndevFrequencyInfo_t": "int version; double boardFreq,ddrFreq;",
        "cndevTemperatureInfo_t": "int version; double board;",
        "cndevUtilizationInfo_t": "int version; double averageCoreUtilization;",
    }
    functions = [
        ("cndevRet_t", "cndevInit", "int flags", "(void)flags; return 0;"),
        ("cndevRet_t", "cndevRelease", "void", "return 0;"),
        (
            "cndevRet_t",
            "cndevGetDeviceCount",
            "cndevCardInfo_t *v",
            "v->number=1; return 0;",
        ),
        (
            "cndevRet_t",
            "cndevGetDeviceHandleByIndex",
            "int index,cndevDevice_t *v",
            "*v=index; return 0;",
        ),
        (
            "cndevRet_t",
            "cndevGetUUID",
            "cndevUUID_t *v,cndevDevice_t d",
            '(void)d; strcpy(v->uuid,"MLU-fixture"); return 0;',
        ),
        (
            "const char *",
            "cndevGetCardNameStringByDevId",
            "cndevDevice_t d",
            '(void)d; return "MLU-mock";',
        ),
        (
            "cndevRet_t",
            "cndevGetVersionInfo",
            "cndevVersionInfo_t *v,cndevDevice_t d",
            "(void)d; v->driverMajorVersion=6; return 0;",
        ),
        (
            "cndevRet_t",
            "cndevGetMemoryUsageV2",
            "cndevMemoryInfoV2_t *v,cndevDevice_t d",
            "(void)d; v->globalMemory=1024; v->physicalMemoryUsed=32; return 0;",
        ),
        (
            "cndevRet_t",
            "cndevGetDevicePowerInfo",
            "cndevDevicePowerInfo_t *v,cndevDevice_t d",
            "(void)d; (void)v; return 3;",
        ),
        (
            "cndevRet_t",
            "cndevGetFrequencyInfo",
            "cndevFrequencyInfo_t *v,cndevDevice_t d",
            "(void)d; v->boardFreq=800; v->ddrFreq=1600; return 0;",
        ),
        (
            "cndevRet_t",
            "cndevGetTemperatureInfo",
            "cndevTemperatureInfo_t *v,cndevDevice_t d",
            "(void)d; v->board=45; return 0;",
        ),
        (
            "cndevRet_t",
            "cndevGetDeviceUtilizationInfo",
            "cndevUtilizationInfo_t *v,cndevDevice_t d",
            "(void)d; v->averageCoreUtilization=25; return 0;",
        ),
    ]
    header = (
        "#define CNDEV_SUCCESS 0\n#define CNDEV_VERSION_6 6\n"
        "typedef int cndevRet_t; typedef int cndevDevice_t;\n"
    )
    header += "\n".join(
        f"typedef struct {{{fields}}} {name};" for name, fields in declarations.items()
    )
    header += "\n" + "\n".join(
        f"{ret} {name}({args});" for ret, name, args, body in functions
    )
    (include / "cndev.h").write_text(header)
    source = "#include <cndev.h>\n#include <string.h>\n" + "\n".join(
        f"{ret} {name}({args}) {{{body}}}" for ret, name, args, body in functions
    )
    (tmp_path / "mock.c").write_text(source)
    suffix = "dylib" if sys.platform == "darwin" else "so"
    command = [
        shutil.which("cc"),
        "-shared",
        "-fPIC",
        f"-I{include}",
        str(tmp_path / "mock.c"),
        "-o",
        str(lib / f"libcndev.{suffix}"),
    ]
    subprocess.run(command, check=True, capture_output=True)
    monkeypatch.setattr(sys, "platform", "linux")
    destination = tmp_path / "omnismi-cndev-probe"
    metadata = build_probe(
        include_dir=str(include), library_dir=str(lib), output=str(destination)
    )
    assert len(metadata["header_sha256"]) == 64
    result = subprocess.run(
        [str(destination), "--snapshot"], text=True, capture_output=True, check=True
    )
    device = mlu.parse_snapshot(result.stdout)["MLU-fixture"]
    assert device["memory_total_bytes"] == 1024**3
    assert device["power_w"] is None
    assert device["return_codes"]["power"] == 3
    with pytest.raises(ValueError, match="new file"):
        build_probe(
            include_dir=str(include), library_dir=str(lib), output=str(destination)
        )
