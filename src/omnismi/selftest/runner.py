"""One isolated, deadline-bounded worker per explicitly selected runtime device."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from .catalog import plan


def read_checkpoint(path, fallback):
    try:
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("checkpoint exceeds 8 MiB")
        report = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(report, dict)
            or report.get("report_type") != "hardware_selftest"
            or report.get("status") not in ("PASS", "FAIL", "INCONCLUSIVE")
            or type(report.get("complete")) is not bool
            or report.get("config") != fallback["config"]
        ):
            raise ValueError("invalid checkpoint schema or configuration")
        return report
    except (OSError, ValueError, TypeError):
        return fallback


def finish(
    report, interrupted=False, returncode=0, interruption_reason="worker_timeout"
):
    if (
        not interrupted
        and returncode == 0
        and report.get("status") == "FAIL"
        and report.get("phase") == "finished"
    ):
        return report  # An intentional first-mismatch stop is not a worker crash.
    if interrupted or returncode != 0 or not report.get("complete"):
        report["complete"] = False
        report.setdefault("errors", []).append(
            {
                "reason": interruption_reason if interrupted else "worker_incomplete",
                "returncode": returncode,
            }
        )
        # Timeout/crash must never erase an earlier numerical failure.
        if report["status"] != "FAIL":
            report["status"] = "INCONCLUSIVE"
    return report


def run(config):
    config.validate()
    fallback = plan(config)
    # Normalize tuples to their JSON representation before validating checkpoints.
    fallback = json.loads(json.dumps(fallback))
    if os.name != "posix":
        fallback["errors"] = [{"reason": "isolated_worker_requires_posix"}]
        return fallback
    with tempfile.TemporaryDirectory(prefix="omnismi-selftest-") as temporary:
        checkpoint = Path(temporary) / "report.json"
        command = [
            sys.executable,
            "-m",
            "omnismi.selftest.worker",
            json.dumps(asdict(config)),
            str(checkpoint),
        ]
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        interrupted = False
        interruption_reason = "worker_timeout"
        try:
            process.wait(timeout=config.timeout)
        except subprocess.TimeoutExpired:
            interrupted = True
        except KeyboardInterrupt:
            interrupted = True
            interruption_reason = "worker_cancelled"
        finally:
            # Reap descendants even if a framework's parent exited first.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        report = read_checkpoint(checkpoint, fallback)
        return finish(report, interrupted, process.returncode, interruption_reason)
