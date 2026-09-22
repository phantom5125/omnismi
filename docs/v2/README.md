# Omnismi 2.0 implementation plan

Status: initial diagnostics, performance comparison, topology and SAIL PPU
implementations are combined on `codex/v2-preview`, 2026-09-22. Independent draft
PRs remain open against `codex/v2-integration`; see [delivery status](STATUS.md)
for exact scope, validation and remaining work. Cambricon is interface research
only. No new backend has been validated on hardware.

## Goal

Give an agent a compact, deterministic, structured answer about accelerator
health, performance and locality in one call. Vendor-document research happens
when maintaining the package, not during each diagnosis. Preserve the small
existing Python API and keep vendor dependencies optional.

## Branches and order

All feature branches start from the same `codex/v2-integration` bootstrap commit,
which descends from `codex/cli-foundation` at `ab1ffd8`. They are sibling branches,
not a chain. Merge reviewed changes into integration, then refresh other branches
only when they need the new contracts. Do not merge integration into `main` until
the existing CLI work is reviewed. Keep the package version unchanged for now.

| Order | Branch | Scope | Feature design on that branch |
|---|---|---|---|
| 1 | `codex/v2-diagnostics` | Offline error knowledge, log normalization, evidence-based diagnosis, explicit self-check | `docs/v2/diagnostics.md` |
| 2 | `codex/v2-perf-doctor` | Reproducible baselines and measured/expected percentages | `docs/v2/perf-doctor.md` |
| 3 | `codex/v2-topology-affinity` | PCIe, NVLink, NUMA, NIC and process affinity | `docs/v2/topology-affinity.md` |
| 4a | `codex/v2-alibaba-ppu` | PPU discovery and normalized metrics | `docs/v2/alibaba-ppu.md` |
| 4b | `codex/v2-cambricon` | Cambricon discovery and normalized metrics | `docs/v2/cambricon.md` |

Diagnostics decoding, performance comparison, topology discovery and vendor
adapters can be implemented independently. Performance *explanation* can consume
diagnostics and topology later; the initial percentage calculator must not depend
on either. Vendor-specific diagnostics and benchmarks follow each adapter's
validated discovery/metrics support.

Existing PR #5 (`feat/agent-preflight-cli`) overlaps the CLI foundation in the CLI
module and documentation. Resolve command dispatch, output schemas, visibility
semantics and exit codes before accepting either implementation into the 2.0
release baseline. Do not blindly merge the two CLI files. The old `dc/test`
hardware-detection changes require separate review for container false negatives.

## Shared report contract (proposed)

- `schema_version`, `report_type`, `tool_version`, `status`, `scope`, `data`,
  `evidence`, `limitations`, `sources`.
- `status`: `PASS`, `WARN`, `FAIL`, `INCONCLUSIVE`. Missing permission, unavailable
  SDK, unsupported hardware and absent baselines are distinct reasons, not healthy
  results. `FAIL` is a failed stated check, not automatically broken hardware.
- Preserve device UUID and PCI BDF when available; report logical/runtime index
  separately. Never join devices across tools using ordinal index alone.
- `scope` records collection time, host/container view and device selection.
  Distinguish unavailable, unsupported, permission denied and actual zero values.
- Evidence has stable IDs, source/collector, timestamp and observed facts.
  Findings reference evidence IDs and document/rule IDs. Do not emit invented
  numeric confidence; use `observed`, `suspected`, `inconclusive` with reasons.
- Compact JSON is the default for new agent commands; stderr carries diagnostics.
  Proposed exit codes: 0 PASS, 1 WARN, 2 FAIL, 3 INCONCLUSIVE, 64 invalid input,
  70 internal failure. Reconcile these with PR #5 before implementation; existing
  commands retain their behavior until an explicit migration is documented.
- Public Python functions return serializable report objects without printing or
  invoking an LLM. Runtime diagnosis has no network dependency.
- Passive collection never resets devices, injects errors, changes affinity or
  reads arbitrary paths requested by log content. Active self-tests and benchmark
  workloads require an explicit execution flag, timeout and resource budget.

Keep command implementations in separate modules; central CLI dispatch should be
a small integration change. Core remains usable without vendor SDKs installed.

## Delivery gates

1. Versioned schemas and source-backed fixtures; implement pure transformations
   first and test unknown, malformed and partial input.
2. Optional, bounded collectors with permission/timeout/error reporting.
3. CLI/Python parity and wheel/sdist data inclusion; offline smoke tests.
4. Hardware evidence with model, SDK, driver, OS, scope and anonymized output;
   publish a capability matrix distinguishing fixture-tested from hardware-tested.
5. Integrated no-vendor regression checks, agent examples and migration notes.

Baseline at branch creation: existing local suite reports 41 passed. This does not
validate these planned features or any physical accelerator.

## Source maintenance

See `sources.json` for initial official references checked on 2026-09-22. This is
a source index, not a completed white-paper corpus. Before implementing a rule,
record the source revision/section, applicability (model/driver), review date and
rule revision. Store original concise summaries and normalized facts; do not
redistribute entire vendor manuals without an appropriate license. Test the
installed offline catalog, including unknown codes and out-of-scope versions.

## Confirmed user scope

PPU work targets the T-Head SAIL SDK using https://developer.t-head.cn/ as the
primary vendor entry (the supplied `/home` route could not be retrieved by the
research tool). Exact SKU and installed SDK version remain open. Cambricon has no
specified target card; do not select a model implicitly or promise model coverage.
