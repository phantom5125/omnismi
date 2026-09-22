"""Offline, provenance-aware performance comparison without guessed baselines."""

from __future__ import annotations

import math
from typing import Any

from omnismi import __version__

SIGNATURE_FIELDS = (
    "vendor",
    "sku",
    "form_factor",
    "partition",
    "memory_mode",
    "probe",
    "probe_version",
    "pattern",
    "dtype",
    "buffer_bytes",
    "byte_convention",
    "runtime",
    "runtime_version",
    "driver_version",
    "device_count",
    "power_limit_w",
    "clock_policy",
)
_UNITS = {"memory_bandwidth": "bytes/s", "compute_throughput": "FLOP/s"}


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def measurement_from_bench(
    report: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
    result_id: str | None = None,
) -> dict[str, Any]:
    """Adapt an existing BenchReport, leaving uncaptured conditions unknown.

    Context may supply missing signature fields but cannot override observed ones.
    Multiple device results require explicit selection within the same report.
    """
    report = _object(report, "BenchReport")
    if (
        report.get("kind") != "BenchReport"
        or report.get("apiVersion") != "omnismi/v1alpha1"
    ):
        raise ValueError("Expected an omnismi/v1alpha1 BenchReport")
    results = report.get("results")
    if not isinstance(results, list) or any(not isinstance(x, dict) for x in results):
        raise ValueError("BenchReport requires results")
    candidates = [
        x for x in results if result_id is None or x.get("result_id") == result_id
    ]
    if len(candidates) != 1:
        raise ValueError("Select exactly one benchmark result with --result-id")
    result = candidates[0]
    execution = _object(result.get("execution"), "execution")
    if result.get("probe") != "bandwidth" or execution.get("status") != "success":
        raise ValueError("Only successful bandwidth results can be compared")
    inventory = _object(report.get("inventory"), "inventory").get("devices")
    if not isinstance(inventory, list) or any(
        not isinstance(d, dict) for d in inventory
    ):
        raise ValueError("Inventory devices must be a list of objects")
    devices = [d for d in inventory if d.get("index") == result.get("device_index")]
    if len(devices) != 1 or result.get("device_index") is None:
        raise ValueError("Benchmark result has ambiguous device identity")
    device = devices[0]
    params = _object(result.get("parameters"), "parameters")
    metrics = _object(result.get("metrics"), "metrics")
    pattern, size = params.get("pattern"), params.get("buffer_bytes")
    factor = {"copy": 2, "triad": 3}.get(pattern) if isinstance(pattern, str) else None
    if (
        factor is None
        or type(size) is not int
        or size <= 0
        or metrics.get("bytes_per_iteration") != factor * size
    ):
        raise ValueError("Unverified benchmark byte accounting")
    metadata = _object(report.get("metadata", {}), "metadata")
    version = metadata.get("omnismi_version")
    signature = {
        "vendor": device.get("vendor"),
        "probe": "bandwidth",
        "probe_version": (
            f"omnismi/{version}/torch-v1" if isinstance(version, str) else None
        ),
        "pattern": pattern,
        "dtype": params.get("dtype"),
        "buffer_bytes": size,
        "byte_convention": "read_plus_write",
        "runtime": params.get("runtime"),
        "driver_version": device.get("driver"),
        "device_count": 1,
    }
    if not metadata.get("omnismi_version"):
        signature["probe_version"] = None
    if context is not None:
        if not isinstance(context, dict) or set(context) - set(SIGNATURE_FIELDS):
            raise ValueError("Context must contain only signature fields")
        for field, value in context.items():
            if signature.get(field) is not None and signature[field] != value:
                raise ValueError(f"Context cannot override recorded {field}")
            signature[field] = value
    return {
        "schema_version": 1,
        "metric": "memory_bandwidth",
        "unit": "bytes/s",
        "value": metrics.get("bandwidth_bytes_per_second"),
        "signature": signature,
        "source": {
            "id": str(metadata.get("run_id") or "provided-bench-report"),
            "description": "BenchReport plus caller-supplied conditions.",
        },
    }


def _number(value: Any, *, positive: bool = False) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and (value > 0 if positive else value >= 0)
    except OverflowError:
        return False


def _source(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("id"), str)
        and bool(value["id"].strip())
        and isinstance(value.get("description"), str)
        and bool(value["description"].strip())
    )


def _source_record(value: dict[str, Any]) -> dict[str, str]:
    return {
        key: value[key]
        for key in ("id", "description", "url")
        if isinstance(value.get(key), str)
    }


def _safe_scalar(value: Any) -> Any:
    return value if value is None or isinstance(value, str) or _number(value) else None


def _valid_signature_value(field: str, value: Any) -> bool:
    if field in {"buffer_bytes", "device_count"}:
        return type(value) is int and value > 0
    if field == "power_limit_w":
        return _number(value, positive=True)
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value.strip().lower() != "unknown"
    )


def evaluate_performance(
    measurement: dict[str, Any], baseline: dict[str, Any] | None
) -> dict[str, Any]:
    """Return ratios only for matching signatures and documented denominators.

    Missing data produces INCONCLUSIVE. Thresholds belong to the supplied baseline,
    not the library. Percentages are never interpreted as hardware utilization.
    """
    if not isinstance(measurement, dict) or measurement.get("schema_version") != 1:
        raise ValueError("Measurement must be a schema_version 1 object")
    if baseline is not None and (
        not isinstance(baseline, dict) or baseline.get("schema_version") != 1
    ):
        raise ValueError("Baseline must be a schema_version 1 object")
    report: dict[str, Any] = {
        "schema_version": 1,
        "report_type": "performance_comparison",
        "tool_version": __version__,
        "status": "INCONCLUSIVE",
        "scope": {"input_kind": "offline_measurement", "hardware_diagnosis": False},
        "data": {
            "baseline_id": baseline.get("baseline_id") if baseline else None,
            "percent_of_expected_sustained": None,
            "percent_of_theoretical_peak": None,
            "mismatches": [],
            "policy_applied": False,
        },
        "evidence": [],
        "limitations": [],
        "sources": [],
    }
    data, reasons = report["data"], report["limitations"]
    if baseline is None:
        reasons.append("baseline_missing")
        return report
    if not isinstance(baseline.get("baseline_id"), str) or not baseline["baseline_id"]:
        raise ValueError("Baseline requires a baseline_id")
    metric = measurement.get("metric")
    if not isinstance(metric, str) or metric not in _UNITS:
        reasons.append("unsupported_metric")
        return report
    if baseline.get("metric") != metric or measurement.get("unit") != _UNITS[metric]:
        reasons.append("metric_or_unit_mismatch")
        return report
    observed = measurement.get("value")
    if not _number(observed):
        reasons.append("measurement_missing_or_nonfinite")
        return report
    if not _source(measurement.get("source")):
        reasons.append("measurement_provenance_missing")
        return report
    report["evidence"].append(
        {
            "id": "measurement",
            "metric": metric,
            "value": observed,
            "unit": measurement["unit"],
            "source": _source_record(measurement["source"]),
        }
    )
    actual = measurement.get("signature", {})
    expected = baseline.get("signature", {})
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        raise ValueError("Signatures must be objects")
    for field in SIGNATURE_FIELDS:
        left, right = actual.get(field), expected.get(field)
        valid = _valid_signature_value(field, left) and _valid_signature_value(
            field, right
        )
        if not valid or left != right:
            data["mismatches"].append(
                {
                    "field": field,
                    "measured": _safe_scalar(left),
                    "expected": _safe_scalar(right),
                    "reason": "missing_or_unknown" if not valid else "different",
                }
            )
    if data["mismatches"]:
        reasons.append("incomparable_signature")
        return report

    references = baseline.get("references", {})
    if not isinstance(references, dict):
        raise ValueError("Baseline references must be an object")
    for name in ("expected_sustained", "theoretical_peak"):
        reference = references.get(name)
        if not isinstance(reference, dict):
            reasons.append(f"{name}_missing")
            continue
        if not _number(reference.get("value"), positive=True):
            reasons.append(f"{name}_invalid_denominator")
            continue
        if reference.get("unit") != _UNITS[metric]:
            reasons.append(f"{name}_unit_mismatch")
            continue
        if not _source(reference.get("source")):
            reasons.append(f"{name}_provenance_missing")
            continue
        if name == "expected_sustained":
            if (
                type(reference.get("sample_count")) is not int
                or reference["sample_count"] < 2
                or not _number(reference.get("standard_deviation"))
                or not isinstance(reference.get("run_ids"), list)
                or not reference["run_ids"]
                or any(not isinstance(x, str) or not x for x in reference["run_ids"])
            ):
                reasons.append("sustained_baseline_evidence_incomplete")
                continue
        percent = observed / reference["value"] * 100
        if not math.isfinite(percent):
            reasons.append(f"{name}_ratio_overflow")
            continue
        data[f"percent_of_{name}"] = percent
        report["sources"].append(
            {"reference": name, **_source_record(reference["source"])}
        )
        report["evidence"].append(
            {
                "id": name,
                "value": reference["value"],
                "unit": reference["unit"],
            }
        )
        if percent > 100:
            reasons.append(f"above_{name}_review_reference_and_measurement")

    policy = baseline.get("policy")
    if policy is None:
        reasons.append("threshold_policy_missing")
    elif not isinstance(policy, dict) or not (
        _number(policy.get("fail_below_percent"))
        and _number(policy.get("pass_at_least_percent"), positive=True)
        and policy["fail_below_percent"] < policy["pass_at_least_percent"] <= 100
        and isinstance(policy.get("rationale"), str)
        and bool(policy["rationale"].strip())
    ):
        raise ValueError(
            "Policy needs 0 <= fail_below < pass_at_least <= 100 and rationale"
        )
    elif data["percent_of_expected_sustained"] is not None:
        percent = data["percent_of_expected_sustained"]
        report["status"] = (
            "FAIL"
            if percent < policy["fail_below_percent"]
            else "PASS" if percent >= policy["pass_at_least_percent"] else "WARN"
        )
        data["policy_applied"] = True
        data["policy"] = {
            key: policy[key]
            for key in ("fail_below_percent", "pass_at_least_percent", "rationale")
        }
    if (data["percent_of_theoretical_peak"] or 0) > 100:
        report["status"] = "INCONCLUSIVE"
        data["policy_applied"] = False
        reasons.append("measurement_exceeds_declared_theoretical_limit")
    reasons.append(
        "Percentages describe this workload comparison, not hardware health."
    )
    return report
