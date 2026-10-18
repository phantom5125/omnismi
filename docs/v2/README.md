# Omnismi 2.0 design and development history

Version 2.0.0 includes active probes, baseline authoring, live topology,
full PPU telemetry, native SAIL workloads and an SDK-compiled Cambricon adapter.
`bench matmul` and `bench suite` now execute bounded probes. See [delivery status](STATUS.md)
for commands, validation and remaining external evidence. No new card has been
hardware-validated or promoted to verified status.

## Goal

Give an agent a compact, deterministic, structured answer about accelerator
health, performance and locality in one call. Vendor-document research happens
when maintaining the package, not during each diagnosis. Preserve the small
existing Python API and keep vendor dependencies optional.

## Original feature branches

The original feature branches started from the same `codex/v2-integration`
bootstrap commit, which descends from `codex/cli-foundation` at `ab1ffd8`.
Their work was assembled in `codex/v2-preview` and completed in
`codex/v2-runtime-completion`. Version 2.0.0 ships the integrated implementation;
new work should start from `main`.

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

PR #5 (`feat/agent-preflight-cli`) is a separate proposal outside the 2.0.0
release. Its admission thresholds, visibility remapping and command compatibility
remain follow-up work; inventory and metrics are available through the overview
CLI. Future integration must preserve the released report and exit-code contracts.

## Shared report contract

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
  New-command exit codes: 0 PASS, 1 WARN, 2 FAIL, 3 INCONCLUSIVE, 64 invalid input.
  Existing overview/doctor/legacy bandwidth commands retain their behavior.
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
