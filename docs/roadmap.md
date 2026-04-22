# Roadmap

Omnismi `1.x` keeps the Python API small and stable while growing the surrounding
tooling that makes the library easier to trust, diagnose, and operationalize.

## Guiding direction

- Keep the public Python contract minimal: `count`, `gpus`, `gpu`, `info`, `metrics`.
- Add richer CLI and reporting layers before adding broader framework-specific APIs.
- Prefer vendor-agnostic diagnostics and benchmarks over vendor demo code when validating hardware.
- Separate three concerns clearly:
  - discovery: what hardware and backends are visible
  - spec modeling: what the machine should be capable of on paper
  - empirical probing: what the machine can actually sustain in practice

This direction is partly informed by projects such as
[`NVlabs/SOLAR`](https://github.com/NVlabs/SOLAR), which separates
hardware-independent analysis from architecture-specific performance prediction.
For Omnismi, the analogous opportunity is to separate hardware discovery from
architecture profiles and portable runtime probes.

## v1.0.x

- Stable minimal API (`count`, `gpus`, `gpu`, `info`, `metrics`)
- NVIDIA + AMD backend support plus experimental Google TPU support
- Unified units and nullable metrics
- Local parity validation workflow

## v1.1.x

Focus: make first-run experience and environment diagnosis much better.

- Expand tested runtime/driver matrix
- Improve per-architecture compatibility notes
- Add more backend diagnostics and debug visibility
- Add a first-class discovery CLI centered on `omnismi`
  for a modern cross-vendor machine summary
- Add a first-class `omnismi doctor` or `omnismi probe` CLI for:
  - backend import status
  - driver/runtime visibility
  - visible devices and normalized inventory
  - clear reasons for unavailable metrics or unavailable backends
- Define and validate host, container, and Kubernetes device-plugin support
  expectations for discovery and diagnostics
- Add direct validation/parity workflow for Google TPU

## v1.2.x

Focus: answer the question "does this machine match the hardware spec I think I rented or bought?"

- Add a normalized machine profile/report surface in the CLI
- Introduce curated accelerator architecture profiles with fields such as:
  - model family / SKU alias
  - memory capacity
  - peak memory bandwidth
  - peak clock ranges where appropriate
  - peak compute throughput by datatype where appropriate
- Add `omnismi validate-spec` style checks that compare:
  - detected inventory vs expected SKU/profile
  - observed total memory vs expected capacity
  - driver/runtime state vs known compatibility expectations
- Emit explicit outcomes such as `PASS`, `WARN`, `FAIL`, and `INCONCLUSIVE`
  instead of vague success text
- Support JSON and Markdown reports so results can be attached to CI, issues, or procurement checks

## v1.3.x

Focus: provide portable, non-vendor benchmark evidence that users can trust.

- Add an `omnismi bench` CLI with small reproducible probes instead of vendor sample apps
- Start with a compact benchmark suite that is feasible across supported vendors:
  - memory bandwidth probe
  - memory capacity pressure / allocation sanity check
  - simple GEMM or matmul throughput probe where runtime support exists
  - repeated-sample stability checks to catch thermal throttling or power caps
- Compare empirical results against architecture-profile expectations and produce a compact health summary
- Export structured results for later comparison across runs, machines, and clusters
- Document how Omnismi benchmarks differ from:
  - parity checks against vendor libraries
  - full profilers
  - vendor marketing or sample benchmarks

## v2.0

Focus: build higher-confidence performance reasoning without bloating the core API.

- Evaluate lower-level bindings to reduce dependency coupling
- Expand long-term compatibility strategy across vendor/runtime drift
- Explore model-aware performance estimation layered on top of Omnismi reports
  rather than folded into the minimal core API
- Revisit scheduler/runtime integration APIs (for example Ray-oriented helpers)
  only after diagnostics, spec validation, and benchmarking surfaces are stable

## Non-goals for now

- Turning Omnismi into a full profiler
- Chasing every vendor-specific benchmark knob in the core package
- Expanding the Python API aggressively before CLI/reporting workflows settle
