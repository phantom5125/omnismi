# Roadmap

Omnismi is a tool for people and agents to inspect, diagnose and validate
accelerators across vendors. The [product direction](why-omnismi.md) defines
portability and framework boundaries. The Python API remains compatible while
the CLI, reports and vendor execution adapters carry new workflows.

## Current delivery

| Track | State | Remaining evidence or implementation |
|---|---|---|
| 2.0 inventory, diagnostics, performance and topology | Published | See [delivery status](v2/STATUS.md) and [hardware compatibility](compatibility.md) |
| 2.1 CPU-reference self-test | Development preview | Target-card validation, native unit coverage and PPU SDC execution |
| Human output for every diagnostic workflow | Planned | Newer commands still primarily emit JSON |
| Machine-readable capability discovery and unified report conventions | Planned | Existing commands have different envelopes, flags and some exit semantics |
| Standalone distribution and MCP wrapper | Future evaluation | Current distribution is a Python package with CLI; neither is shipped |

## Next: validate the 2.1 self-test workflow

1. Keep topk independent from sort, retain complete CPU comparisons and
   reproducible failures, and collect reports from normal and known-faulty cards.
2. Add native per-workload SM/CU/unit observations. Distinguish sampled scheduling
   units from coverage of internal arithmetic units, memory banks and links.
3. Add genuinely concurrent load/check phases where supported, and record whether
   requested power conditions were observed. Preserve every checked output.
4. Implement PPU SAIL SDC execution and validate MLU/TPU/AMD adapters against their
   actual SDK/card matrix. Unsupported paths remain explicit.

The [2.1 guide](v2.1/hardware-selftest.md) contains current commands, limitations and
acceptance criteria. These steps do not promise a particular release date or full
hardware certification.

## Next: complete the human and agent tool interfaces

- Render concise human findings and next steps from the same reports used by
  agents. Add a consistent output-selection convention without silently breaking
  existing command behavior.
- Publish schemas and compatibility rules for device identity, report scope,
  sources, timestamps, units, verdicts and evidence artifacts. Migrate existing
  report envelopes deliberately; do not claim they are already identical.
- Expose machine-readable command/backend capabilities, prerequisites and reasons
  for unavailable checks. Agents should discover support rather than trial-run
  every vendor command or read SDK manuals during each invocation.
- Unify device selection around resolved identities while retaining management
  indexes, runtime indexes, visibility masks and partition boundaries as evidence.
- Keep offline interpretation and planning usable without a compute runtime;
  require explicit execution for workloads with memory/time budgets.

Accept these interfaces with one shared inspection/validation client running
against supported vendor fixtures and actual hardware reports. The client should
change selection/configuration, not implement separate parsing or verdict logic
for each vendor. Missing capabilities must be testable outcomes.

## Later: deployment and ecosystem integrations

- Evaluate isolated CLI installation, reproducible containers and standalone
  packages based on host compatibility. Python remains the implementation today;
  removing the need for users to write Python does not require an immediate rewrite.
- Add SDK or MCP integrations only when they reuse the established report and
  execution contracts. Do not maintain a second diagnostic implementation.
- Let schedulers and deployment systems consume readiness, affinity and performance
  evidence; add integration helpers only for concrete workflows.
- Expand vendor support and validation matrices without forcing all hardware into
  a lowest-common-denominator metric or feature set.

General tensor computation, autograd, model compilation and arbitrary model
migration remain responsibilities of compute frameworks. Omnismi may use their
operators and native SDK kernels as diagnostic instruments.
