"""Independent percentage calculations, comparability and policy boundaries."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from omnismi.cli import main
from omnismi.performance import (
    SIGNATURE_FIELDS,
    evaluate_performance,
    measurement_from_bench,
)


@pytest.fixture
def pair():
    signature = {
        "vendor": "test",
        "sku": "synthetic",
        "form_factor": "pcie",
        "partition": "whole",
        "memory_mode": "ecc",
        "probe": "bandwidth",
        "probe_version": "1",
        "pattern": "copy",
        "dtype": "fp32",
        "buffer_bytes": 268435456,
        "byte_convention": "read_plus_write",
        "runtime": "torch",
        "runtime_version": "test",
        "driver_version": "test",
        "device_count": 1,
        "power_limit_w": 300,
        "clock_policy": "default",
    }
    source = {"id": "synthetic", "description": "Test arithmetic, not hardware data"}
    measured = {
        "schema_version": 1,
        "metric": "memory_bandwidth",
        "unit": "bytes/s",
        "signature": signature,
        "value": 800,
        "source": source,
    }
    baseline = {
        "schema_version": 1,
        "baseline_id": "synthetic-only",
        "metric": "memory_bandwidth",
        "signature": deepcopy(signature),
        "references": {
            "expected_sustained": {
                "value": 1000,
                "unit": "bytes/s",
                "source": source,
                "sample_count": 3,
                "standard_deviation": 10,
                "run_ids": ["synthetic-run"],
            },
            "theoretical_peak": {"value": 2000, "unit": "bytes/s", "source": source},
        },
        "policy": {
            "fail_below_percent": 70,
            "pass_at_least_percent": 90,
            "rationale": "Synthetic test thresholds only",
        },
    }
    return measured, baseline


def test_independent_denominators_and_no_input_mutation(pair):
    measured, baseline = pair
    before = deepcopy(pair)
    report = evaluate_performance(measured, baseline)
    assert report["data"]["percent_of_expected_sustained"] == 80
    assert report["data"]["percent_of_theoretical_peak"] == 40
    assert report["status"] == "WARN"
    assert report["data"]["policy_applied"]
    assert pair == before


@pytest.mark.parametrize(
    "value,status",
    [
        (0, "FAIL"),
        (699, "FAIL"),
        (700, "WARN"),
        (899, "WARN"),
        (900, "PASS"),
        (1100, "PASS"),
    ],
)
def test_exact_policy_boundaries(pair, value, status):
    measured, baseline = pair
    measured["value"] = value
    report = evaluate_performance(measured, baseline)
    assert report["status"] == status
    if value == 1100:
        assert report["data"]["percent_of_expected_sustained"] == pytest.approx(110)
        assert any("above_expected" in item for item in report["limitations"])


@pytest.mark.parametrize("field", SIGNATURE_FIELDS)
def test_every_required_signature_dimension_blocks_invalid_comparison(pair, field):
    measured, baseline = pair
    measured["signature"].pop(field)
    report = evaluate_performance(measured, baseline)
    assert report["status"] == "INCONCLUSIVE"
    assert report["data"]["percent_of_expected_sustained"] is None
    assert report["data"]["mismatches"][0]["field"] == field


@pytest.mark.parametrize("bad", [0, -1, None, float("nan"), float("inf"), True])
def test_invalid_denominators_cannot_generate_ratios(pair, bad):
    measured, baseline = pair
    baseline["references"]["expected_sustained"]["value"] = bad
    report = evaluate_performance(measured, baseline)
    assert report["status"] == "INCONCLUSIVE"
    assert report["data"]["percent_of_expected_sustained"] is None
    json.dumps(report, allow_nan=False)


def test_units_sources_and_empirical_evidence_are_required(pair):
    measured, baseline = pair
    for key, replacement in [
        ("unit", "GB/s"),
        ("source", {}),
        ("sample_count", 1),
        ("standard_deviation", None),
        ("run_ids", []),
    ]:
        candidate = deepcopy(baseline)
        candidate["references"]["expected_sustained"][key] = replacement
        assert evaluate_performance(measured, candidate)["status"] == "INCONCLUSIVE"
    measured["unit"] = "GiB/s"
    assert evaluate_performance(measured, baseline)["status"] == "INCONCLUSIVE"


def test_missing_baseline_or_thresholds_and_above_theoretical_peak(pair):
    measured, baseline = pair
    assert evaluate_performance(measured, None)["status"] == "INCONCLUSIVE"
    policy = baseline.pop("policy")
    report = evaluate_performance(measured, baseline)
    assert report["status"] == "INCONCLUSIVE"
    assert report["data"]["percent_of_expected_sustained"] == 80
    baseline["policy"] = policy
    measured["value"] = 2100
    report = evaluate_performance(measured, baseline)
    assert report["status"] == "INCONCLUSIVE"
    assert report["data"]["percent_of_theoretical_peak"] == 105
    assert not report["data"]["policy_applied"]


def test_signature_mismatch_nonfinite_values_and_invalid_policy(pair):
    measured, baseline = pair
    measured["signature"]["power_limit_w"] = float("nan")
    report = evaluate_performance(measured, baseline)
    json.dumps(report, allow_nan=False)
    assert report["status"] == "INCONCLUSIVE"
    measured["signature"]["power_limit_w"] = 300
    baseline["policy"]["fail_below_percent"] = 95
    with pytest.raises(ValueError, match="Policy"):
        evaluate_performance(measured, baseline)


def test_cli_json_and_explicit_invalid_legacy_format(pair, tmp_path, capsys):
    measured, baseline = pair
    measurement_path, baseline_path = (
        tmp_path / "measurement.json",
        tmp_path / "baseline.json",
    )
    measurement_path.write_text(json.dumps(measured))
    baseline_path.write_text(json.dumps(baseline))
    assert (
        main(
            [
                "perf-doctor",
                "--input",
                str(measurement_path),
                "--baseline",
                str(baseline_path),
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["status"] == "WARN"
    measurement_path.write_text('{"kind":"BenchReport"}')
    assert main(["perf-doctor", "--input", str(measurement_path)]) == 64
    assert "BenchReport" in capsys.readouterr().err


def test_existing_bench_import_preserves_observations_and_requires_selection():
    report = {
        "apiVersion": "omnismi/v1alpha1",
        "kind": "BenchReport",
        "metadata": {"omnismi_version": "1.0.0", "run_id": "test-run"},
        "inventory": {"devices": [{"index": 0, "vendor": "nvidia", "driver": "550"}]},
        "results": [
            {
                "result_id": "r0",
                "device_index": 0,
                "probe": "bandwidth",
                "execution": {"status": "success"},
                "parameters": {
                    "pattern": "copy",
                    "dtype": "fp32",
                    "buffer_bytes": 100,
                    "runtime": "torch",
                },
                "metrics": {
                    "bandwidth_bytes_per_second": 800,
                    "bytes_per_iteration": 200,
                },
            }
        ],
    }
    measured = measurement_from_bench(report)
    assert measured["value"] == 800
    assert measured["signature"]["driver_version"] == "550"
    assert "runtime_version" not in measured["signature"]
    with pytest.raises(ValueError, match="override"):
        measurement_from_bench(report, context={"driver_version": "555"})
    other = deepcopy(report["results"][0])
    other["result_id"] = "r1"
    report["results"].append(other)
    with pytest.raises(ValueError, match="exactly one"):
        measurement_from_bench(report)
    assert measurement_from_bench(report, result_id="r0")["value"] == 800
    report["results"][0]["metrics"]["bytes_per_iteration"] = 100
    with pytest.raises(ValueError, match="accounting"):
        measurement_from_bench(report, result_id="r0")
