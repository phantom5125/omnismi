"""Deterministic interpretations of supplied evidence, never hardware verdicts."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from omnismi import __version__
from omnismi.diagnostics.catalog import load_catalog
from omnismi.diagnostics.parsers import (
    MAX_EVENTS,
    clean_text,
    parse_events,
    parse_log,
    parse_ras_counts,
)

_CONTEXT_KEYS = {"driver_version", "model"}


def _context(context: dict[str, str] | None) -> dict[str, str]:
    if context is None:
        return {}
    if not isinstance(context, dict) or set(context) - _CONTEXT_KEYS:
        raise ValueError("Context supports only driver_version and model")
    if any(not isinstance(v, str) or len(v) > 128 for v in context.values()):
        raise ValueError("Context values must be strings of at most 128 characters")
    return {k: clean_text(v) for k, v in context.items()}


def _finding(
    vendor: str, namespace: str, code: str | None, catalog: dict[str, Any]
) -> dict[str, Any]:
    rule = next(
        (
            item
            for item in catalog["rules"]
            if (vendor, namespace, code)
            == (item["vendor"], item["namespace"], item["code"])
        ),
        None,
    )
    if rule is None:
        return {
            "rule_id": None,
            "vendor": vendor,
            "namespace": namespace,
            "code": code,
            "recognized": False,
            "status": "INCONCLUSIVE",
            "assessment": "inconclusive",
            "hardware_assessment": "unconfirmed",
            "summary": "No reviewed rule matches this vendor, namespace and code.",
            "affected_units": [],
            "source_ids": [],
            "next_checks": [],
            "evidence_ids": [],
        }
    finding = deepcopy(rule)
    finding["rule_id"] = finding.pop("id")
    finding.update(
        recognized=True,
        status=(
            "FAIL"
            if rule["severity"] == "critical"
            else "INCONCLUSIVE" if rule["severity"] == "informational" else "WARN"
        ),
        assessment="observed_event",
        hardware_assessment="unconfirmed",
        evidence_ids=[],
    )
    finding["next_checks"] = [
        {"id": key, "description": catalog["actions"][key], "executed": False}
        for key in rule["next_checks"]
    ]
    return finding


def _report(
    report_type: str, catalog: dict[str, Any], context: dict[str, str]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "report_type": report_type,
        "tool_version": __version__,
        "catalog_revision": catalog["catalog_revision"],
        "status": "INCONCLUSIVE",
        "scope": {
            "input_kind": "provided_evidence",
            "reported_at": datetime.now(timezone.utc).isoformat(),
            "context": context,
            "current_hardware_health": "INCONCLUSIVE",
            "status_meaning": "severity_of_supplied_evidence_not_current_health",
        },
        "data": {},
        "evidence": [],
        "limitations": [
            "Curated subset; unrecognized events need additional investigation.",
            "No physical unit failure is confirmed by this report.",
            "Event age, recovery, model and driver applicability need verification.",
        ],
        "sources": [],
    }


def _finish(report: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    findings = report["data"]["findings"]
    model = report["scope"]["context"].get("model", "").upper()
    family = re.fullmatch(r"(?:NVIDIA\s+)?(A100|H100|B100|GB200)(?:[ -].*)?", model)
    if family:
        for finding in findings:
            flags = finding.get("catalog_model_applicability", {})
            applies = flags.get(family[1])
            finding["model_applicability"] = applies
            if applies is False:
                finding["status"] = "INCONCLUSIVE"
                finding["assessment"] = "catalog_model_mismatch"
                report["limitations"].append(
                    "Catalog excludes the supplied model for an observed code."
                )
    # Repeated observations share an explanation; evidence still keeps each line.
    # This is output deduplication, not a causal or temporal inference.
    compact: dict[tuple[Any, ...], dict[str, Any]] = {}
    recognized = sum(bool(f["recognized"]) for f in findings)
    for finding in findings:
        key = tuple(
            finding.get(k)
            for k in (
                "vendor",
                "namespace",
                "code",
                "pci_address",
                "uuid",
                "block",
                "status",
            )
        )
        if key not in compact:
            compact[key] = finding
            finding["occurrences"] = 1
        else:
            compact[key]["occurrences"] += 1
            compact[key]["evidence_ids"].extend(finding["evidence_ids"])
    report["data"]["findings"] = list(compact.values())
    statuses = {item["status"] for item in findings}
    if "FAIL" in statuses:
        report["status"] = "FAIL"
    elif "WARN" in statuses:
        report["status"] = "WARN"
    # Absence of known errors, including zero counters, never proves health.
    used_sources = {sid for item in findings for sid in item["source_ids"]}
    report["sources"] = [s for s in catalog["sources"] if s["id"] in used_sources]
    report["data"]["coverage"] = {
        "recognized": recognized,
        "unrecognized": len(findings) - recognized,
        "complete_catalog": False,
    }
    return report


def decode_error(
    vendor: str,
    namespace: str,
    code: str | int,
    *,
    context: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Explain an error in one offline call; no collection or remediation occurs."""
    for value in (vendor, namespace):
        if not isinstance(value, str) or not re.fullmatch(
            r"[a-z][a-z0-9_-]{0,31}", value
        ):
            raise ValueError("Vendor and namespace must be lower-case identifiers")
    if isinstance(code, bool) or not isinstance(code, (str, int)):
        raise ValueError("Code must be a string or integer")
    code = str(code).lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,63}", code):
        raise ValueError("Invalid error code")
    if namespace.startswith("xid") and code.isdecimal():
        code = str(int(code))
    catalog = load_catalog()
    report = _report("error_decode", catalog, _context(context))
    report["data"]["findings"] = [_finding(vendor, namespace, code, catalog)]
    report["scope"]["input_kind"] = "code_lookup"
    if report["data"]["findings"][0]["recognized"]:
        report["data"]["findings"][0]["assessment"] = "code_meaning_only"
    return _finish(report, catalog)


def diagnose(
    text: str,
    *,
    input_format: str = "dmesg",
    block: str | None = None,
    pci_address: str | None = None,
    context: dict[str, str] | None = None,
    include_raw: bool = False,
    max_events: int = MAX_EVENTS,
) -> dict[str, Any]:
    """Interpret a bounded log or a single identified AMD RAS counter snapshot.

    Timestamp/identity are preserved per event. No cross-line causality, reset,
    current-health verdict or inferred device mapping is asserted.
    """
    if input_format not in {"dmesg", "ras", "events"}:
        raise ValueError("Supported input formats: dmesg, ras, events")
    if type(max_events) is not int or not 1 <= max_events <= MAX_EVENTS:
        raise ValueError("max_events must be between 1 and 500")
    if input_format == "ras":
        if not block or not pci_address:
            raise ValueError("RAS input requires block and pci_address")
        parsed = parse_ras_counts(text, block=block, pci_address=pci_address)
        if len(parsed["events"]) > max_events:
            parsed["events"] = parsed["events"][:max_events]
            parsed["limitations"].append("event_limit_reached")
    else:
        if block is not None or pci_address is not None:
            raise ValueError("block and pci_address apply only to RAS input")
        parsed = (
            parse_events(text, max_events=max_events)
            if input_format == "events"
            else parse_log(text, max_events=max_events)
        )
    catalog = load_catalog()
    report = _report("diagnosis", catalog, _context(context))
    report["scope"]["input_format"] = input_format
    report["limitations"].extend(parsed["limitations"])
    findings = []
    for event in parsed["events"]:
        finding = _finding(event["vendor"], event["namespace"], event["code"], catalog)
        finding["evidence_ids"] = [event["id"]]
        finding["pci_address"] = event["pci_address"]
        finding["block"] = event["block"]
        if event.get("uuid"):
            finding["uuid"] = event["uuid"]
        if event["namespace"] == "ras":
            finding["affected_units"] = [f"ras:{event['block']}"]
            if event["count"] == 0:
                finding["status"] = "INCONCLUSIVE"
                finding["summary"] = "No errors counted in this snapshot field."
            finding["assessment"] = "observed_counter_snapshot"
        findings.append(finding)
        evidence = {k: v for k, v in event.items() if k != "raw_text"}
        if include_raw:
            evidence["raw_text"] = event["raw_text"]
        report["evidence"].append(evidence)
    report["data"]["findings"] = findings
    if not findings:
        report["limitations"].append(
            "No events supplied; absence is not a health check."
        )
    return _finish(report, catalog)
