"""Reproducible sustained baseline construction from retained measurements."""

from __future__ import annotations

import copy
import json
import statistics
from typing import Any

from omnismi.performance import (
    SIGNATURE_FIELDS,
    _number,
    _source,
    _valid_signature_value,
)


def build_baseline(
    measurements: list[dict[str, Any]],
    *,
    baseline_id: str,
    policy: dict[str, Any] | None = None,
    theoretical_peak: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an auditable mean/stddev baseline; never invent run conditions."""
    if not isinstance(baseline_id, str) or not baseline_id.strip():
        raise ValueError("A baseline ID is required")
    if not isinstance(measurements, list) or not 2 <= len(measurements) <= 1000:
        raise ValueError("A baseline requires 2..1000 distinct measurements")
    first = measurements[0]
    if not isinstance(first, dict):
        raise ValueError("Measurements must be objects")
    signature = first.get("signature")
    if not isinstance(signature, dict) or any(
        not _valid_signature_value(key, signature.get(key)) for key in SIGNATURE_FIELDS
    ):
        raise ValueError("Every baseline condition must be known")
    metric, unit = first.get("metric"), first.get("unit")
    if not isinstance(metric, str) or not isinstance(unit, str):
        raise ValueError("Metric and unit must be strings")
    if {"memory_bandwidth": "bytes/s", "compute_throughput": "FLOP/s"}.get(
        metric
    ) != unit:
        raise ValueError("Unknown metric or unit")
    ids, values = set(), []
    for item in measurements:
        if (
            not isinstance(item, dict)
            or type(item.get("schema_version")) is not int
            or item["schema_version"] != 1
            or item.get("metric") != metric
            or item.get("unit") != unit
            or item.get("signature") != signature
            or not _number(item.get("value"), positive=True)
            or not _source(item.get("source"))
        ):
            raise ValueError(
                "Measurements must be valid, positive and exactly comparable"
            )
        run_id = item["source"]["id"]
        if run_id in ids:
            raise ValueError(
                "Duplicate run ID; repeating one observation is not sampling"
            )
        ids.add(run_id)
        values.append(item["value"])
    if policy is not None and (
        not isinstance(policy, dict)
        or not _number(policy.get("fail_below_percent"))
        or not _number(policy.get("pass_at_least_percent"), positive=True)
        or not policy["fail_below_percent"] < policy["pass_at_least_percent"] <= 100
        or not isinstance(policy.get("rationale"), str)
        or not policy["rationale"].strip()
    ):
        raise ValueError("Policy requires ordered thresholds and a rationale")
    if theoretical_peak is not None and (
        not isinstance(theoretical_peak, dict)
        or theoretical_peak.get("unit") != unit
        or not _number(theoretical_peak.get("value"), positive=True)
        or not _source(theoretical_peak.get("source"))
    ):
        raise ValueError("Theoretical peak requires a positive value, unit and source")
    try:
        json.dumps(measurements, allow_nan=False)
        mean, deviation = statistics.fmean(values), statistics.stdev(values)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Nonserializable measurements or statistics overflow") from exc
    if not _number(mean, positive=True) or not _number(deviation):
        raise ValueError("Baseline statistics overflow")
    baseline = {
        "schema_version": 1,
        "baseline_id": baseline_id,
        "metric": metric,
        "signature": copy.deepcopy(signature),
        "references": {
            "expected_sustained": {
                "value": mean,
                "unit": unit,
                "sample_count": len(values),
                "standard_deviation": deviation,
                "coefficient_of_variation": deviation / mean,
                "run_ids": sorted(ids),
                "source": {
                    "id": baseline_id,
                    "description": "Mean of retained independent measurements.",
                },
            }
        },
        "measurements": copy.deepcopy(measurements),
    }
    if policy is not None:
        baseline["policy"] = copy.deepcopy(policy)
    if theoretical_peak is not None:
        baseline["references"]["theoretical_peak"] = copy.deepcopy(theoretical_peak)
    return baseline
