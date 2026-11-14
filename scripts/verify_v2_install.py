"""Offline installed-wheel checks; never starts an accelerator workload."""

import json
import os
import subprocess
import sys
import tempfile
from importlib.metadata import version
from importlib.resources import files

import omnismi
from omnismi.diagnostics import decode_error
from omnismi.diagnostics.catalog import load_catalog

assert "site-packages" in omnismi.__file__, "Install the wheel without PYTHONPATH first"
assert version("omnismi") == omnismi.__version__, "Package and runtime versions differ"
assert len(load_catalog()["rules"]) == 273
assert files("omnismi.backends").joinpath("cndev_probe.c").is_file()
assert files("omnismi.backends").joinpath("sail_probe.hg").is_file()
assert files("omnismi.backends").joinpath("sail_probe_host.hpp").is_file()
assert decode_error("nvidia", "xid", 119)["data"]["findings"][0]["recognized"]
assert decode_error("alibaba", "xid-ppu0015", 4997)["status"] == "FAIL"
environment = dict(os.environ)
environment.pop("PYTHONPATH", None)
with tempfile.TemporaryDirectory() as temporary:
    for command in (
        "",
        "doctor",
        "validate-spec",
        "bench bandwidth",
        "decode",
        "diagnose",
        "perf-doctor",
        "topology",
        "cndev-build",
        "sail-build",
        "bench matmul",
        "bench suite",
        "preflight",
        "inventory",
        "metrics",
        "version",
    ):
        result = subprocess.run(
            [sys.executable, "-m", "omnismi", *command.split(), "--help"],
            cwd=temporary,
            env=environment,
            text=True,
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0, (command, result.stderr)
    for command in ("version", "--version"):
        result = subprocess.run(
            [sys.executable, "-m", "omnismi", command],
            cwd=temporary,
            env=environment,
            text=True,
            capture_output=True,
            timeout=10,
        )
        expected = (
            omnismi.__version__
            if command == "version"
            else f"omnismi {omnismi.__version__}"
        )
        assert result.returncode == 0 and result.stdout.strip() == expected
    for command in ("preflight", "inventory", "metrics"):
        result = subprocess.run(
            [sys.executable, "-m", "omnismi", command],
            cwd=temporary,
            env={**environment, "CUDA_VISIBLE_DEVICES": ""},
            text=True,
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 2, (command, result.stderr)
        snapshot = json.loads(result.stdout)
        assert snapshot["command"] == command
        assert snapshot["exit_code"] == 2
        assert snapshot["ts_ns"] > 0
        assert snapshot["summary"]["gpu_count"] == 0
    for argument in ("--min-gpus=-1", "--min-free-gib=nan", "--min-free-gib=1e308"):
        result = subprocess.run(
            [sys.executable, "-m", "omnismi", "preflight", argument],
            cwd=temporary,
            env=environment,
            text=True,
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 1, (argument, result.stderr)
        assert result.stdout == "" and "error:" in result.stderr
    result = subprocess.run(
        [sys.executable, "-m", "omnismi", "diagnose", "--input", "-"],
        input="[ 1.0] NVRM: Xid (PCI:0000:03:00): 48, observed error\n",
        cwd=temporary,
        env=environment,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert (
        json.loads(result.stdout)["scope"]["current_hardware_health"] == "INCONCLUSIVE"
    )
print("Installed wheel: 16 CLI helps, admission contracts, catalog and sources passed")
