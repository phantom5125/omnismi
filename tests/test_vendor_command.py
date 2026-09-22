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
