"""Offline installed-wheel checks; never starts an accelerator workload."""

import json
import os
import subprocess
import sys
import tempfile
from importlib.metadata import version
from importlib.resources import files

import omnismi
from omnismi.dashboard.server import create_server
from omnismi.diagnostics import decode_error
from omnismi.diagnostics.catalog import load_catalog
from omnismi.selftest.targets import target_catalog

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
        "decode",
        "diagnose",
        "perf-doctor",
        "topology",
        "cndev-build",
        "sail-build",
        "bench matmul",
        "bench suite",
        "self-test",
        "dashboard",
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
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "omnismi",
            "self-test",
            "--plan",
            "--target",
            "rtx-5090",
        ],
        cwd=temporary,
        env=environment,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["executed"] is False
    assert json.loads(result.stdout)["target"]["id"] == "rtx-5090"
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

assert len(target_catalog()["targets"]) == 4
server = create_server(0)
assert server.server_address[0] == "127.0.0.1"
server.server_close()
assert files("omnismi.dashboard").joinpath("static/index.html").is_file()
assert (
    files("omnismi.dashboard")
    .joinpath("static/assets/third-party-licenses.txt")
    .is_file()
)
print(
    "Installed wheel: catalog, native sources, ten CLI entry points "
    "dashboard assets and target self-test plan passed"
)
