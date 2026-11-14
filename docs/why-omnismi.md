# Why Omnismi

## The problem

Accelerator work often starts with vendor-specific questions: which devices are
visible inside this container, why can the framework see fewer devices than the
host, what does this error code mean, and did the selected device actually run a
correct workload? Vendor tools remain the source of truth, but their commands,
object models, units, and failure modes differ.

Omnismi turns those recurring tasks into one operational CLI for humans and AI
agents, with a small Python API for applications that need in-process metrics.
It is an inspection and evidence tool, not another monitoring daemon.

## Target users

- AI and coding agents that need bounded, structured accelerator inspection.
- Platform engineers debugging device visibility, telemetry, errors, and locality.
- Performance engineers comparing measurements with their own recorded baselines.
- Python application developers who want one accelerator API across vendors.

## Why vendor tools alone leave a gap

Vendor tools and bindings are the source of truth, and Omnismi depends on them.
The gap appears when an agent or application must perform the same task across
multiple vendors: command discovery, field normalization, error interpretation,
report handling, and runtime-visibility checks otherwise become separate branches.

Omnismi adds a consistent task layer while retaining vendor evidence and explicit
limitations. It does not claim to replace advanced vendor profiling or management.

## Why framework memory APIs are not enough

PyTorch and other framework APIs are valuable for runtime-level diagnosis, but
they are scoped to that framework and process. They do not provide a general
cross-vendor management view, offline error catalog, host topology report, or
lightweight agent workflow for non-framework processes.

## What Omnismi adds

- A human-first overview with plain-language `doctor` findings and next steps.
- Structured agent reports with explicit verdicts, scope, evidence, sources,
  and limitations.
- Offline interpretation that never confuses a recorded event with current
  hardware health.
- Explicit, bounded workloads instead of hidden benchmarks during discovery.
- A stable Python contract: `count`, `gpus`, `gpu`, `info`, and `metrics`.
- Normalized units and unavailable values represented as `None`.
- Clear separation between implemented adapters and validated hardware models.

## Non-goals

- Omnismi is not a full profiler or a complete replacement for vendor tooling.
- Omnismi does not install drivers, SDKs, or compute frameworks.
- Omnismi does not hide platform, permission, or runtime constraints.
- Omnismi does not guarantee every metric on every device or infer health from
  missing evidence.
