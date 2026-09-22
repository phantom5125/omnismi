"""Bounded execution for fixed, read-only vendor management commands."""

from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time

from omnismi.errors import BackendError


def query_text(argv: list[str]) -> str:
    """Run a fixed vendor query on POSIX, with a 5-second/1-MiB total budget."""
    if os.name != "posix":
        raise BackendError("Vendor command collection currently requires POSIX")
    limit = 1_048_576
    process = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        env={**os.environ, "LC_ALL": "C"},
    )
    assert process.stdout is not None and process.stderr is not None
    chunks: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = time.monotonic() + 5
    reaped = False
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise BackendError("Vendor query timed out")
                for key, _ in selector.select(remaining):
                    chunk = os.read(key.fileobj.fileno(), 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    elif sum(len(v) for v in chunks.values()) + len(chunk) > limit:
                        raise BackendError("Vendor query output exceeds 1 MiB")
                    else:
                        chunks[key.data].extend(chunk)
            try:
                process.wait(timeout=max(0.001, deadline - time.monotonic()))
                reaped = True
            except subprocess.TimeoutExpired as exc:
                raise BackendError("Vendor query timed out") from exc
        if process.returncode:
            raise BackendError(f"Vendor query failed (exit {process.returncode})")
        return bytes(chunks["stdout"]).decode("utf-8", errors="strict")
    finally:
        # On interrupted collection, children can still hold the query pipes.
        # Once wait() reaps the child, its PID may be reused: never signal it.
        if not reaped:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        process.stdout.close()
        process.stderr.close()
