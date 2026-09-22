"""Bounded subprocess collection exercised without native accelerator tools."""

from __future__ import annotations

import os
import sys

import pytest

from omnismi.backends.command import query_text
from omnismi.errors import BackendError


@pytest.mark.skipif(os.name != "posix", reason="POSIX command adapter")
def test_command_stdout_errors_and_budget():
    assert query_text([sys.executable, "-c", "print('ok')"]) == "ok\n"
    with pytest.raises(BackendError, match="exit 7"):
        query_text([sys.executable, "-c", "import sys; sys.exit(7)"])
    with pytest.raises(BackendError, match="exceeds"):
        query_text([sys.executable, "-c", "print('x' * 1100000)"])


@pytest.mark.skipif(os.name != "posix", reason="POSIX command adapter")
def test_completed_query_never_signals_reaped_process(monkeypatch):
    def unexpected_signal(*args):
        pytest.fail("A reaped process group must not be signaled")

    monkeypatch.setattr(os, "killpg", unexpected_signal)
    assert query_text([sys.executable, "-c", "print('ok')"]) == "ok\n"
    with pytest.raises(BackendError, match="exit 7"):
        query_text([sys.executable, "-c", "import sys; sys.exit(7)"])


@pytest.mark.skipif(os.name != "posix", reason="POSIX command adapter")
def test_query_timeout_reaps_process_group(monkeypatch):
    signaled = []
    real_killpg = os.killpg

    def record_signal(pid, sig):
        signaled.append(pid)
        real_killpg(pid, sig)

    monkeypatch.setattr(os, "killpg", record_signal)
    with pytest.raises(BackendError, match="timed out"):
        query_text([sys.executable, "-c", "import time; time.sleep(30)"])
    assert len(signaled) == 1
    with pytest.raises(ChildProcessError):
        os.waitpid(signaled[0], os.WNOHANG)
