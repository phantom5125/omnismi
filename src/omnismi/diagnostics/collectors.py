"""Explicit passive collection with bounded output and wall time."""

from __future__ import annotations

import math
import os
import selectors
import shutil
import signal
import subprocess
import sys
import time
from typing import Any

from omnismi.diagnostics.parsers import MAX_BYTES


def collect_kernel_log(
    *, timeout: float = 5.0, max_bytes: int = MAX_BYTES
) -> dict[str, Any]:
    """Read dmesg on Linux, without sudo, clearing the ring buffer or a shell.

    Permission failures, timeout and truncation remain explicit. Partial stdout
    may be analyzed, but it never implies collection succeeded.
    """
    if not math.isfinite(timeout) or not 0 < timeout <= 60:
        raise ValueError("timeout must be finite and in (0, 60] seconds")
    if not 1 <= max_bytes <= MAX_BYTES:
        raise ValueError("Invalid collector byte limit")
    result: dict[str, Any] = {
        "collector": "kernel_log",
        "status": "unavailable",
        "reason": None,
        "returncode": None,
        "text": "",
        "timeout_seconds": timeout,
        "output_limit_bytes": max_bytes,
    }
    if sys.platform != "linux":
        result.update(status="unsupported", reason="linux_required")
        return result
    executable = shutil.which("dmesg")
    if executable is None:
        result["reason"] = "dmesg_not_found"
        return result
    try:
        process = subprocess.Popen(
            [executable],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            env={**os.environ, "LC_ALL": "C"},
        )
    except OSError:
        result["reason"] = "launch_failed"
        return result

    output: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = time.monotonic() + timeout
    stop_reason = None
    assert process.stdout is not None and process.stderr is not None
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    stop_reason = "timeout"
                    break
                for key, _ in selector.select(remaining):
                    chunk = os.read(key.fileobj.fileno(), 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    capacity = max_bytes - sum(len(v) for v in output.values())
                    output[key.data].extend(chunk[:capacity])
                    if len(chunk) > capacity:
                        stop_reason = "output_truncated"
                        break
                if stop_reason:
                    break
            if stop_reason is None:
                try:
                    process.wait(timeout=max(0.001, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    stop_reason = "timeout"
    finally:
        # Kill the owned process group if its deadline/output budget was exceeded.
        # A child keeping a pipe open must not outlive the collection request.
        if stop_reason or process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait()
        process.stdout.close()
        process.stderr.close()

    raw = bytes(output["stdout"])
    if stop_reason:
        raw = raw.rsplit(b"\n", 1)[0] if b"\n" in raw else b""
    result["text"] = raw.decode("utf-8", errors="replace")
    result["returncode"] = process.returncode
    if stop_reason:
        result.update(status="partial", reason=stop_reason)
    elif process.returncode != 0:
        error = bytes(output["stderr"]).lower()
        permission = (
            b"operation not permitted" in error or b"permission denied" in error
        )
        result.update(
            status="permission_denied" if permission else "error",
            reason="kernel_log_access_denied" if permission else "dmesg_failed",
        )
    else:
        result.update(status="ok")
    return result
