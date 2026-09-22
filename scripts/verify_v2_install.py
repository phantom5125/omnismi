"""Offline installed-wheel checks; never starts an accelerator workload."""

import json
import os
import subprocess
import sys
import tempfile
from importlib.resources import files

import omnismi
from omnismi.diagnostics import decode_error
from omnismi.diagnostics.catalog import load_catalog

assert "site-packages" in omnismi.__file__, "Install the wheel without PYTHONPATH first"
assert len(load_catalog()["rules"]) == 273
assert files("omnismi.backends").joinpath("cndev_probe.c").is_file()
assert decode_error("nvidia", "xid", 119)["data"]["findings"][0]["recognized"]
assert decode_error("alibaba", "xid-ppu0015", 4997)["status"] == "FAIL"
environment = dict(os.environ)
environment.pop("PYTHONPATH", None)
with tempfile.TemporaryDirectory() as temporary:
    for command in ("decode", "diagnose", "perf-doctor", "topology", "cndev-build"):
        result = subprocess.run(
            [sys.executable, "-m", "omnismi", command, "--help"],
            cwd=temporary,
            env=environment,
            text=True,
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0, (command, result.stderr)
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
print(
    "Installed wheel: catalog, native source and five CLI entry points passed"
)
