# Agent-native diagnosis and offline error knowledge

Status: planned; this branch contains the implementation contract, not a working decoder.

## User-facing contract

Proposed Python: `decode_error(vendor, namespace, code, context=None)` and
`diagnose(events, inventory=None, observations=None)`. Proposed commands:

```text
omnismi decode --vendor nvidia --namespace xid --code 48
omnismi diagnose --input kernel.log --format dmesg
omnismi diagnose --collect passive
omnismi diagnose --self-test --timeout 60
```

Each call returns the shared JSON envelope. `decode` is a pure offline lookup;
`diagnose` normalizes and correlates supplied evidence; passive collection is
explicit; self-test has a separate execution path. Log ingestion never runs text
from input as a command. Limit bytes/events and report truncation.

## Knowledge model

Each rule contains vendor, namespace (Xid, SXid, AMD RAS, PCIe AER), code/block,
applicable architectures and driver versions, short explanation, severity,
possible affected units, alternative software/environment causes, evidence needed,
next checks, source section/revision and catalog revision. Use independent namespaces:
RAS block/counter events and arbitrary dmesg messages are not interchangeable with Xid.

Store original summaries and normalized facts in a packaged, versioned catalog.
Review against the official references in `sources.json`; online updates are a
maintenance operation, never an implicit part of an agent request. Unknown codes,
unknown driver versions and ambiguous matches retain raw evidence with explicit
coverage limits. A recognized error is not proof of a defective memory bank or die.

Findings include `affected_units` (memory, compute, PCIe, interconnect, power/thermal,
unknown), `assessment`, `evidence_ids`, `alternative_causes`, `next_checks`, and
`source_ids`. Localize only to the granularity explicitly supported by the evidence.
Use a consistent device identity and bounded time window for correlation. Preserve
correctable vs uncorrectable and historical counts vs new deltas; old log entries
must not silently represent current health. An empty/inaccessible log is inconclusive.

## Implementation sequence

1. `diagnostics/catalog.py` and catalog package data: validate schema/provenance,
   deterministic matching, pure decode API. First curated rules: a reviewed subset
   of Xids covering memory, compute and link symptoms; no fabricated completeness.
2. `diagnostics/parsers.py`: NVRM Xid fixtures, AMD RAS block/counter fixtures,
   generic unmatched dmesg events; normalize timestamp, device identity and scope.
3. `diagnostics/engine.py`: evidence-linked findings, unknown coverage and compact
   JSON. Do not overwrite a known device identity with a process-local index.
4. `diagnostics/collectors.py`: bounded kernel-log and vendor read-only telemetry,
   collector status and access failures. Self-tests expose their requirements and
   workload impact; no reset, RAS injection or automatic remediation.
5. Wire CLI and add source/catalog revision to every report. Later extend specific
   rules for PPU/Cambricon only after official error documentation is obtained.

## Acceptance

Offline one-call decoding works from an installed wheel without an LLM or internet.
Every explanation has a source and applicability. Tests cover unknown codes,
malformed logs, multi-device correlation, stale events, ANSI/control characters,
ambiguous dates, missing permission, timeouts, truncation and wrong driver versions.
Synthetic cases cannot claim hardware-confirmed diagnosis. Real logs/self-tests
require per-vendor hardware evidence before marking that path validated.
