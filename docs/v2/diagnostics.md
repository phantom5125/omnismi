# Agent-native diagnosis and offline error knowledge

Status: first implementation available on `codex/v2-diagnostics`; fixture-tested,
not hardware-validated. Active self-tests and causal event correlation remain planned.

## Available now

The library runs offline without vendor dependencies. Its packaged catalog has 15
reviewed rules: NVIDIA Xid 13/31/43/48/63/64/74/79/94/95, AMD RAS ce/ue counter
semantics, and PCIe AER corrected/nonfatal/fatal severity. PPU Xid and NVIDIA SXid
are intentionally not mapped to NVIDIA Xid rules. The full vendor code catalog is
not implemented. Each interpretation includes source URLs, source revisions,
catalog revision, applicability limits, possible affected units and suggested checks.

```python
from omnismi.diagnostics import decode_error, diagnose

report = decode_error("nvidia", "xid", 48)
report = diagnose("[ 10.5] NVRM: Xid (0000:03:00): 79, device unreachable")
report = diagnose(
    "ue: 0\nce: 5", input_format="ras", block="umc", pci_address="0000:41:00.0"
)
```

```bash
omnismi decode --vendor nvidia --namespace xid --code 48
omnismi diagnose --input kernel.log
cat kernel.log | omnismi diagnose --input -
omnismi diagnose --input umc-counts.txt --format ras --block umc --pci-address 0000:41:00.0
omnismi diagnose --collect passive --timeout 5
```

New commands always output JSON. `--driver-version` and `--model` retain supplied
context; they do not certify model/driver applicability. `--include-raw` adds
sanitized source lines; by default only normalized evidence is emitted. Repeated
findings on the same reported device share one explanation and retain all evidence
IDs, reducing repeated text for agents. This grouping makes no causal inference.

These commands use exits 0 PASS, 1 WARN, 2 FAIL, 3 INCONCLUSIVE and 64 invalid input.
Existing commands are unchanged. Here WARN/FAIL describe the supplied event severity,
not present hardware health. `scope.current_hardware_health` remains INCONCLUSIVE.
Unknown codes, empty logs and zero counter snapshots never prove a healthy device.

Passive collection reads Linux `dmesg` only, without sudo, clearing logs or changing
hardware state. Missing tools, access denial, truncation and timeout are explicit.
There is no collection during ordinary `decode` or `diagnose --input` calls.
Limits: 1 MiB input, 500 nonblank events (lower with `--max-events`), 4096 characters
per line, and at most 60 seconds for collection. A truncated code is never decoded
as a different complete code. Regular file input must be UTF-8; named pipes use stdin.

RAS input is the documented sysfs counter format, with explicit block/PCI identity;
arbitrary AMD RAS prose in dmesg remains unmatched. dmesg parsing recognizes NVRM
Xid and PCIe AER severity lines. Other lines are preserved as unrecognized evidence.
Boot-relative timestamps are retained without inventing dates; wall-clock parsing,
GPU UUID association, event freshness, reset history and cross-line causality are
not yet implemented. Missing PCI function numbers are not invented for joins.

## Remaining milestones

- Version-specific catalog expansion and official PPU/Cambricon error references.
- More vendor log fixtures, identity/time normalization and corroboration rules.
- Read-only device telemetry beyond kernel logs, then explicit active self-tests.
- Real-device validation; no fixture result can upgrade hardware support status.

## User-facing contract

Longer-term API and commands (the self-test command is not implemented):

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
