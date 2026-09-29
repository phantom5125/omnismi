"""Real bounded subprocess behavior using a fake dmesg executable."""

from __future__ import annotations

import os
import sys
import time

import pytest

from omnismi.diagnostics import collectors


@pytest.fixture
def fake_dmesg(tmp_path, monkeypatch):
    if os.name != "posix":
        pytest.skip("POSIX subprocess collection")
    path = tmp_path / "dmesg"
    monkeypatch.setattr(collectors.sys, "platform", "linux")
    monkeypatch.setattr(collectors.shutil, "which", lambda _: str(path))

    def write(script):
        path.write_text(f"#!{sys.executable}\n" + script)
        path.chmod(0o700)

    return write


def test_success_and_permission_denial(fake_dmesg):
    fake_dmesg("print('NVRM: Xid (0000:03:00): 48, detail')\n")
    result = collectors.collect_kernel_log()
    assert result["status"] == "ok"
    assert "Xid" in result["text"]
    fake_dmesg(
        "import sys\nprint('Operation not permitted', file=sys.stderr)\nsys.exit(1)\n"
    )
    result = collectors.collect_kernel_log()
    assert result["status"] == "permission_denied"
    assert result["returncode"] == 1


def test_timeout_and_output_budget(fake_dmesg):
    fake_dmesg("import time\ntime.sleep(10)\n")
    before = time.monotonic()
    result = collectors.collect_kernel_log(timeout=0.1)
    assert result["reason"] == "timeout"
    assert time.monotonic() - before < 3
    fake_dmesg("print('x' * 10000)\n")
    result = collectors.collect_kernel_log(max_bytes=128)
    assert result["reason"] == "output_truncated"
    assert len(result["text"]) <= 128


def test_unsupported_platform_and_missing_tool(monkeypatch):
    monkeypatch.setattr(collectors.sys, "platform", "darwin")
    assert collectors.collect_kernel_log()["status"] == "unsupported"
    monkeypatch.setattr(collectors.sys, "platform", "linux")
    monkeypatch.setattr(collectors.shutil, "which", lambda _: None)
    assert collectors.collect_kernel_log()["reason"] == "dmesg_not_found"


@pytest.mark.parametrize("timeout", [0, -1, 61, float("nan"), float("inf")])
def test_bad_timeout_is_rejected(timeout):
    with pytest.raises(ValueError):
        collectors.collect_kernel_log(timeout=timeout)
