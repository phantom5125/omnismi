"""Bundled viewer, local-only HTTP boundary, and report file contracts."""

import http.client
import json
import re
import threading

import pytest

from omnismi.dashboard.server import MAX_REPORT_BYTES, create_server, read_report, run
from omnismi.selftest.catalog import Config, plan


@pytest.fixture
def server():
    payload = json.dumps(plan(Config("nvidia", target="rtx-5090"))).encode()
    server = create_server(0, payload)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def request(server, route="/", method="GET", headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        connection.request(method, route, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def test_bundled_assets_and_preloaded_plan(server):
    assert server.server_address[0] == "127.0.0.1"
    status, headers, body = request(server)
    assert status == 200
    assert b'<div id="root"' in body
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["Cache-Control"] == "no-store"
    for path in re.findall(rb'(?:src|href)="(/assets/[^\"]+)"', body):
        status, headers, asset = request(server, path.decode())
        assert status == 200 and asset
        assert headers["X-Content-Type-Options"] == "nosniff"
    status, _, payload = request(server, "/report.json")
    report = json.loads(payload)
    assert status == 200
    assert report["executed"] is False
    assert report["target"]["hardware_validation"] == "pending"


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "evil.example"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_cross_site_and_untrusted_host_cannot_read_report(server, headers):
    assert request(server, "/report.json", headers=headers)[0] == 403


@pytest.mark.parametrize(
    "route",
    [
        "/../../pyproject.toml",
        "/assets/%2e%2e/%2e%2e/server.py",
        "/server.py",
        "/assets/does-not-exist.js",
    ],
)
def test_server_does_not_expose_local_files(server, route):
    assert request(server, route)[0] == 404


def test_http_cannot_launch_workloads(server):
    assert request(server, "/run", method="POST")[0] == 405


def test_report_file_limits_and_nonfinite_values(tmp_path):
    path = tmp_path / "report.json"
    valid = plan(Config("google", target="tpu-v6e"))
    path.write_text(json.dumps(valid))
    assert json.loads(read_report(path)) == json.loads(json.dumps(valid))
    for payload in ["[]", '{"schema_version":2}', "not json"]:
        path.write_text(payload)
        with pytest.raises(ValueError):
            read_report(path)
    valid["invalid"] = float("nan")
    path.write_text(json.dumps(valid))
    with pytest.raises(ValueError):
        read_report(path)
    path.write_bytes(b" " * (MAX_REPORT_BYTES + 1))
    with pytest.raises(ValueError, match="8 MiB"):
        read_report(path)
    assert run(["--report", str(path)]) == 64
    assert run(["--port", "-1"]) == 64
