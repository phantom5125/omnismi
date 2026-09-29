"""Serve bundled assets on loopback; never execute workloads from HTTP."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import unquote, urlsplit

MAX_REPORT_BYTES = 8 * 1024 * 1024


def read_report(path):
    with Path(path).open("rb") as stream:
        payload = stream.read(MAX_REPORT_BYTES + 1)
    if len(payload) > MAX_REPORT_BYTES:
        raise ValueError("report exceeds 8 MiB")
    report = json.loads(payload)
    if (
        not isinstance(report, dict)
        or report.get("schema_version") != 1
        or report.get("report_type") != "hardware_selftest"
        or report.get("status") not in ("PASS", "FAIL", "INCONCLUSIVE")
    ):
        raise ValueError(
            "expected an Omnismi hardware_selftest schema_version=1 report"
        )
    return json.dumps(report, ensure_ascii=False, allow_nan=False).encode()


def create_server(port=8765, report=None):
    assets = Path(str(files("omnismi.dashboard").joinpath("static"))).resolve()
    if not (assets / "index.html").is_file():
        raise ValueError(
            "dashboard assets missing; build frontend or reinstall the wheel"
        )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):  # noqa: N802
            expected = {
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            }
            if (
                self.headers.get("Host") not in expected
                or self.headers.get("Sec-Fetch-Site") == "cross-site"
            ):
                self.send_error(403)
                return
            route = unquote(urlsplit(self.path).path)
            if route == "/report.json":
                payload, mime = report or b"null", "application/json"
            else:
                name = "index.html" if route == "/" else route.lstrip("/")
                candidate = (assets / name).resolve()
                if (
                    assets not in candidate.parents
                    or not candidate.is_file()
                    or not (name == "index.html" or name.startswith("assets/"))
                ):
                    self.send_error(404)
                    return
                payload = candidate.read_bytes()
                mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", f"{mime}; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; "
                "object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):  # noqa: N802
            self.send_error(405, "This dashboard does not execute workloads")

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def run(argv):
    parser = argparse.ArgumentParser(
        prog="omnismi dashboard",
        description="Open a local self-test report dashboard. "
        "No HTTP workload execution.",
    )
    parser.add_argument(
        "--report", help="Optionally preload one self-test JSON report."
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--open", action="store_true", help="Open the local URL in a browser."
    )
    args = parser.parse_args(argv)
    try:
        if not 0 <= args.port <= 65535:
            raise ValueError("port must be in [0, 65535]")
        payload = read_report(args.report) if args.report else None
        server = create_server(args.port, payload)
    except (ValueError, OSError) as exc:
        print(f"omnismi dashboard: {exc}", file=sys.stderr)
        return 64
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Omnismi dashboard: {url}\nLocal report viewer; Ctrl+C to stop.", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
