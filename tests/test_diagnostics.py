"""Offline diagnostic contracts and adversarial/partial evidence."""

from __future__ import annotations

import json

import pytest

from omnismi.cli import main
from omnismi.diagnostics import decode_error, diagnose, parse_log, parse_ras_counts
from omnismi.diagnostics.catalog import load_catalog
from omnismi.diagnostics.parsers import MAX_LINE


def test_catalog_is_offline_versioned_and_has_resolvable_sources():
    catalog = load_catalog()
    assert len(catalog["rules"]) == 273
    for rule in catalog["rules"]:
        finding = decode_error(rule["vendor"], rule["namespace"], rule["code"])
        assert finding["data"]["findings"][0]["recognized"]
        assert finding["sources"]
        assert all(s["url"].startswith("https://") for s in finding["sources"])
        assert finding["catalog_revision"] == catalog["catalog_revision"]
    catalog["rules"].clear()
    assert load_catalog()["rules"]


@pytest.mark.parametrize(
    "vendor,namespace,code",
    [
        ("nvidia", "xid", 999),
        ("alibaba", "xid", 48),
        ("nvidia", "sxid", 48),
        ("cambricon", "xid", 48),
    ],
)
def test_unknown_vendor_namespace_or_code_is_not_borrowed(vendor, namespace, code):
    report = decode_error(vendor, namespace, code)
    assert report["status"] == "INCONCLUSIVE"
    assert not report["sources"]
    assert report["data"]["coverage"]["unrecognized"] == 1


def test_decode_does_not_assert_failed_hardware_or_validate_driver():
    report = decode_error("nvidia", "xid", "0048", context={"driver_version": "999.0"})
    finding = report["data"]["findings"][0]
    assert finding["code"] == "48"
    assert finding["hardware_assessment"] == "unconfirmed"
    assert finding["assessment"] == "code_meaning_only"
    assert finding["applicability"]["level"] == "generic_meaning_only"
    assert all(not check["executed"] for check in finding["next_checks"])
    assert report["scope"]["current_hardware_health"] == "INCONCLUSIVE"


def test_multiple_devices_and_unknown_lines_remain_separate():
    report = diagnose(
        "[ 12.5] NVRM: Xid (0000:03:00): 48, detail\n"
        "[ 13.1] NVRM: Xid (0000:04:00.1): 13, pid=5\n"
        "2020-01-01T00:00:00Z unrecognized old event\n",
        include_raw=True,
    )
    assert len(report["evidence"]) == 3
    assert report["evidence"][0]["pci_address"] == "0000:03:00"
    assert report["evidence"][1]["pci_address"] == "0000:04:00.1"
    assert report["evidence"][0]["timestamp"] == "12.5"
    assert report["evidence"][2]["time_basis"] == "unknown"
    assert report["status"] == "FAIL"  # logged severity, not a live health check
    assert report["data"]["coverage"]["unrecognized"] == 1
    for finding, evidence in zip(report["data"]["findings"], report["evidence"]):
        assert finding["evidence_ids"] == [evidence["id"]]


def test_no_evidence_or_unrecognized_evidence_never_means_healthy():
    for text in (
        "",
        "boot succeeded",
        "NVRM: Xid (broken): 48",
        "NVRM: Xid (0000:03:00): 48.9",
    ):
        assert diagnose(text)["status"] == "INCONCLUSIVE"


def test_duplicate_explanations_are_compact_but_evidence_is_preserved():
    report = diagnose("NVRM: Xid (0000:03:00): 13, app\n" * 5)
    assert len(report["data"]["findings"]) == 1
    finding = report["data"]["findings"][0]
    assert finding["occurrences"] == 5
    assert len(set(finding["evidence_ids"])) == 5
    assert report["data"]["coverage"]["recognized"] == 5


@pytest.mark.parametrize(
    "severity,code",
    [
        ("Corrected", "corrected"),
        ("Uncorrectable (Non-Fatal)", "nonfatal"),
        ("Uncorrectable (Fatal)", "fatal"),
    ],
)
def test_pcie_reporting_identity_is_not_assumed_to_be_gpu(severity, code):
    report = diagnose(
        f"0000:50:00.0: PCIe Bus Error: severity={severity}, type=Physical"
    )
    evidence = report["evidence"][0]
    assert evidence["vendor"] == "pci"
    assert evidence["code"] == code
    assert evidence["pci_address"] == "0000:50:00.0"
    assert report["data"]["findings"][0]["hardware_assessment"] == "unconfirmed"


def test_ras_counts_are_not_rates_or_new_failures():
    report = diagnose(
        "ue: 0\nce: 5", input_format="ras", block="umc", pci_address="0000:41:00.0"
    )
    assert report["status"] == "WARN"
    assert [e["count"] for e in report["evidence"]] == [0, 5]
    assert all(e["count_semantics"] == "snapshot_not_delta" for e in report["evidence"])
    assert report["data"]["findings"][0]["status"] == "INCONCLUSIVE"
    assert report["data"]["findings"][0]["affected_units"] == ["ras:umc"]
    assert report["scope"]["current_hardware_health"] == "INCONCLUSIVE"
    assert (
        diagnose(
            "ue: 0\nce: 0", input_format="ras", block="gfx", pci_address="0000:41:00.0"
        )["status"]
        == "INCONCLUSIVE"
    )


def test_bare_ras_counts_need_explicit_identity_and_prose_is_unmatched():
    with pytest.raises(ValueError, match="requires"):
        diagnose("ue: 1", input_format="ras")
    assert diagnose("amdgpu RAS initialized successfully")["status"] == "INCONCLUSIVE"
    with pytest.raises(ValueError, match="Duplicate"):
        parse_ras_counts("ce: 1\nce: 2", block="umc", pci_address="0000:01:00.0")
    parsed = parse_ras_counts("ce: 1\nue: -1", block="umc", pci_address="0000:01:00.0")
    assert "incomplete_ras_snapshot" in parsed["limitations"]


def test_input_and_line_limits_do_not_decode_a_cut_code():
    parsed = parse_log("NVRM: Xid (0000:03:00): 480", max_bytes=25)
    assert parsed["events"] == []
    assert "input_bytes_truncated" in parsed["limitations"]
    parsed = parse_log("NVRM: Xid (0000:03:00): 48," + "x" * MAX_LINE)
    assert parsed["events"][0]["code"] is None
    assert "line_truncated" in parsed["limitations"]
    parsed = parse_log("one\ntwo\nthree", max_events=2)
    assert len(parsed["events"]) == 2
    assert "event_limit_reached" in parsed["limitations"]


def test_terminal_escapes_and_untrusted_log_text_never_execute(tmp_path):
    target = tmp_path / "must-not-exist"
    line = f"\x1b[31mNVRM: Xid (0000:03:00): 48, $(touch {target})\x1b[0m\u202e"
    report = diagnose(line, include_raw=True)
    raw = report["evidence"][0]["raw_text"]
    assert "\x1b" not in raw and "\u202e" not in raw
    assert not target.exists()
    assert "raw_text" not in diagnose(line)["evidence"][0]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"vendor": "NVIDIA", "namespace": "xid", "code": 48},
        {"vendor": "nvidia", "namespace": "xid", "code": True},
        {"vendor": "nvidia", "namespace": "xid", "code": "$(whoami)"},
        {
            "vendor": "nvidia",
            "namespace": "xid",
            "code": 48,
            "context": {"run": "sudo"},
        },
    ],
)
def test_decode_rejects_invalid_arguments(kwargs):
    with pytest.raises(ValueError):
        decode_error(**kwargs)


def test_cli_decode_json_and_invalid_input_exit_codes(capsys):
    assert (
        main(["decode", "--vendor", "nvidia", "--namespace", "xid", "--code", "48"])
        == 2
    )
    captured = capsys.readouterr()
    assert not captured.err
    assert json.loads(captured.out)["report_type"] == "error_decode"
    assert main(["decode", "--vendor", "nvidia"]) == 64
    captured = capsys.readouterr()
    assert not captured.out
    assert "required" in captured.err


def test_cli_file_input_and_ras_validation(tmp_path, capsys):
    path = tmp_path / "kernel.log"
    path.write_text("NVRM: Xid (0000:03:00): 13, app")
    assert main(["diagnose", "--input", str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["data"]["coverage"]["recognized"] == 1
    assert main(["diagnose", "--input", str(path), "--format", "ras"]) == 64
    assert "requires" in capsys.readouterr().err
    assert main(["diagnose", "--input", str(tmp_path)]) == 64
    assert "regular file" in capsys.readouterr().err


def test_cli_passive_collection_preserves_failure(monkeypatch, capsys):
    from omnismi.diagnostics import cli

    monkeypatch.setattr(
        cli,
        "collect_kernel_log",
        lambda **_: {
            "collector": "kernel_log",
            "status": "permission_denied",
            "reason": "kernel_log_access_denied",
            "text": "",
        },
    )
    assert main(["diagnose", "--collect", "passive"]) == 3
    report = json.loads(capsys.readouterr().out)
    assert report["data"]["collection"]["status"] == "permission_denied"
    assert any("incomplete" in item for item in report["limitations"])
    assert main(["diagnose", "--collect", "passive", "--format", "ras"]) == 64


def test_large_utf8_file_does_not_fail_on_artificial_read_boundary(tmp_path, capsys):
    from omnismi.diagnostics.parsers import MAX_BYTES

    path = tmp_path / "large.log"
    path.write_text("NVRM: Xid (0000:03:00): 13, detail\n" + "中" * MAX_BYTES)
    assert main(["diagnose", "--input", str(path)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert "input_bytes_truncated" in report["limitations"]
    assert report["data"]["coverage"]["recognized"] == 1
