"""Bounded parsers for kernel logs and explicitly identified AMD RAS counters."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

MAX_BYTES = 1_048_576
MAX_EVENTS = 500
MAX_LINE = 4096
_ANSI = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]")
_BDF = r"[0-9a-fA-F]{4,8}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}(?:\.[0-7])?"
_XID = re.compile(rf"\bNVRM:\s*Xid\s*\(\s*(?:PCI:)?({_BDF})\):\s*(\d+)(?=\s|,|$)", re.I)
_GPU_ID = re.compile(rf"\bNVRM:\s*GPU at\s+({_BDF}):\s*(GPU-[a-f0-9-]+)\b", re.I)
_AER = re.compile(
    r"\bPCIe Bus Error:\s*severity=(Corrected|Uncorrectable\s*\((?:Non-Fatal|Fatal)\))",
    re.I,
)
_TIME = re.compile(r"^\[\s*(\d+(?:\.\d+)?)\]")
_RAS_COUNT = re.compile(r"^(ce|ue):\s*(\d+)\s*$", re.I)


def clean_text(text: str) -> str:
    """Remove terminal control sequences, including Unicode formatting controls."""
    return "".join(
        c for c in _ANSI.sub("", text) if c == "\t" or unicodedata.category(c)[0] != "C"
    )


def normalize_pci_address(value: str) -> str:
    """Preserve a missing function; never invent .0 to correlate two devices."""
    if not isinstance(value, str) or not re.fullmatch(_BDF, value):
        raise ValueError("Expected a PCI address such as 0000:03:00.0")
    domain, bus, device = value.lower().split(":")
    if int(device.split(".")[0], 16) > 31:
        raise ValueError("PCI device number exceeds 31")
    return f"{int(domain, 16):04x}:{bus}:{device}"


def _limits(text: str, max_bytes: int, max_events: int) -> tuple[str, list[str]]:
    if not isinstance(text, str):
        raise ValueError("Input must be text")
    if (
        type(max_bytes) is not int
        or type(max_events) is not int
        or not 1 <= max_bytes <= MAX_BYTES
        or not 1 <= max_events <= MAX_EVENTS
    ):
        raise ValueError("Input limits exceed supported bounds")
    # Slice before encoding to bound transient allocation for very large strings.
    raw = text[: max_bytes + 1].encode("utf-8")
    truncated = len(text) > max_bytes or len(raw) > max_bytes
    bounded = raw[:max_bytes].decode("utf-8", errors="ignore")
    if truncated:
        # A cut code (e.g. 480 -> 48) must not become a different recognized error.
        bounded = bounded.rsplit("\n", 1)[0] if "\n" in bounded else ""
    return bounded, (["input_bytes_truncated"] if truncated else [])


def parse_log(
    text: str, *, max_bytes: int = MAX_BYTES, max_events: int = MAX_EVENTS
) -> dict[str, Any]:
    """Normalize individual lines; never treat arbitrary dmesg as an error code.

    All nonblank lines survive up to the limits, including unrecognized records.
    Time is retained as boot-relative evidence, never assumed to be wall time.
    """
    text, limitations = _limits(text, max_bytes, max_events)
    events = []
    identities: dict[str, str] = {}
    for line_number, original in enumerate(text.splitlines(), 1):
        if not original.strip():
            continue
        if len(events) >= max_events:
            limitations.append("event_limit_reached")
            break
        line_truncated = len(original) > MAX_LINE
        if line_truncated:
            limitations.append("line_truncated")
        line = clean_text(original[:MAX_LINE])
        digest = hashlib.sha256(f"{line_number}:{line}".encode()).hexdigest()[:16]
        timestamp = _TIME.match(line)
        event: dict[str, Any] = {
            "id": f"event-{digest}",
            "line_number": line_number,
            "vendor": "unknown",
            "namespace": "dmesg",
            "code": None,
            "pci_address": None,
            "timestamp": timestamp.group(1) if timestamp else None,
            "time_basis": "boot_relative" if timestamp else "unknown",
            "raw_text": line,
            "count": None,
            "count_semantics": None,
            "block": None,
        }
        xid, aer = _XID.search(line), _AER.search(line)
        gpu_id = _GPU_ID.search(line)
        if gpu_id and not line_truncated:
            try:
                identities[normalize_pci_address(gpu_id[1])] = gpu_id[2]
            except ValueError:
                limitations.append("invalid_pci_address")
        if line_truncated:
            pass
        elif xid:
            event.update(vendor="nvidia", namespace="xid", code=str(int(xid[2])))
            try:
                event["pci_address"] = normalize_pci_address(xid[1])
                if event["pci_address"] in identities:
                    event["uuid"] = identities[event["pci_address"]]
                    event["identity_source"] = "preceding_driver_identity_line"
            except ValueError:
                limitations.append("invalid_pci_address")
        elif aer:
            severity = aer[1].lower()
            code = "corrected" if severity == "corrected" else "fatal"
            if "non-fatal" in severity:
                code = "nonfatal"
            event.update(vendor="pci", namespace="aer", code=code)
            address = re.search(_BDF, line[: aer.start()])
            if address:
                try:
                    event["pci_address"] = normalize_pci_address(address[0])
                except ValueError:
                    limitations.append("invalid_pci_address")
        events.append(event)
    return {"events": events, "limitations": sorted(set(limitations))}


def parse_ras_counts(text: str, *, block: str, pci_address: str) -> dict[str, Any]:
    """Parse the kernel's ce:/ue: snapshot format with caller-supplied identity.

    Bare counters contain neither device identity nor block: both are required.
    Unsupported dmesg RAS prose remains unparsed rather than guessing its format.
    """
    if not isinstance(block, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", block):
        raise ValueError("RAS block must be a lower-case block identifier")
    address = normalize_pci_address(pci_address)
    result = parse_log(text)
    seen = set()
    for event in result["events"]:
        match = _RAS_COUNT.fullmatch(event["raw_text"].strip())
        if match:
            code = match[1].lower()
            if code in seen:
                raise ValueError("Duplicate RAS counter; supply one snapshot at a time")
            seen.add(code)
            event.update(
                vendor="amd",
                namespace="ras",
                code=code,
                count=int(match[2]),
                count_semantics="snapshot_not_delta",
                block=block,
                pci_address=address,
            )
    if seen != {"ce", "ue"}:
        result["limitations"].append("incomplete_ras_snapshot")
    return result


def parse_events(text: str, *, max_events: int = MAX_EVENTS) -> dict[str, Any]:
    """Accept normalized JSON observations from vendor collectors or agents."""
    text, limitations = _limits(text, MAX_BYTES, max_events)
    if limitations:
        raise ValueError("Normalized event JSON exceeds the input budget")
    items = json.loads(text)
    if not isinstance(items, list) or len(items) > max_events:
        raise ValueError("Expected a bounded JSON event array")
    events = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError("Each normalized event must be an object")
        vendor, namespace, code = (
            item.get("vendor"),
            item.get("namespace"),
            item.get("code"),
        )
        if any(
            not isinstance(x, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", x)
            for x in (vendor, namespace)
        ):
            raise ValueError("Event requires an explicit vendor and namespace")
        if type(code) not in (int, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9_.-]{0,63}", str(code)
        ):
            raise ValueError("Invalid normalized event code")
        code = str(int(code)) if str(code).isdecimal() else str(code)
        address = item.get("pci_address")
        if address is not None:
            address = normalize_pci_address(address)
        timestamp = item.get("timestamp")
        basis = item.get("time_basis", "unknown")
        if basis not in {"unknown", "boot_relative"} or (
            timestamp is not None
            and (
                not isinstance(timestamp, str)
                or not re.fullmatch(r"\d{1,12}(?:\.\d{1,9})?", timestamp)
            )
        ):
            raise ValueError("Only explicit boot-relative timestamps are accepted")
        if namespace == "ras":
            raise ValueError("Use RAS format with counter/block semantics")
        events.append(
            {
                "id": f"normalized-{index}",
                "line_number": index + 1,
                "vendor": vendor,
                "namespace": namespace,
                "code": code,
                "pci_address": address,
                "timestamp": timestamp,
                "time_basis": basis,
                "block": None,
                "count": None,
                "count_semantics": None,
                "raw_text": "",
            }
        )
    return {"events": events, "limitations": []}
