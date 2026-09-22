"""Bounded parsers for kernel logs and explicitly identified AMD RAS counters."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

MAX_BYTES = 1_048_576
MAX_EVENTS = 500
MAX_LINE = 4096
_ANSI = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]")
_BDF = r"[0-9a-fA-F]{4,8}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}(?:\.[0-7])?"
_XID = re.compile(rf"\bNVRM:\s*Xid\s*\(({_BDF})\):\s*(\d+)(?=\s|,|$)", re.I)
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
        if line_truncated:
            pass
        elif xid:
            event.update(vendor="nvidia", namespace="xid", code=str(int(xid[2])))
            try:
                event["pci_address"] = normalize_pci_address(xid[1])
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
