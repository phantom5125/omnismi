# Changelog

## [Unreleased]

## [2.0.0] - 2026-09-30

### Added

- Structured agent commands for offline error decoding, hardware evidence collection,
  bounded self-tests, performance comparison, and topology discovery.
- An offline catalog of 273 source-backed rules covering NVIDIA Xids, Alibaba PPU
  error generations, and RAS/AER/ECC events, with explicit unknown/inconclusive results.
- `perf-doctor` with recorded conditions, repeated measurements, baseline creation,
  and percentages of expected sustained performance and theoretical peak.
- Linux PCI/NUMA/NIC/RDMA discovery, live NVIDIA NVLink/MIG and Alibaba ICN topology,
  and affinity suggestions constrained by the process's effective masks.
- Optional Alibaba SAIL PPU telemetry and native HGGC probes, plus a Cambricon
  collector compiled against the installed CNDEV SDK.
- `bench matmul` and `bench suite` with bounded workloads and correctness checks.
- Human-readable overview, `doctor`, and `validate-spec` CLI commands alongside
  JSON output and the existing Python API.
- English and Chinese quickstarts, installed-wheel smoke checks, and CI across
  Linux Python 3.9/3.10/3.12/3.14 and macOS Python 3.12.
- Experimental Google TPU backend backed by `libtpu.sdk.tpumonitoring`

### Changed

- Package and runtime versions are now `2.0.0`; documentation and CI badges point
  to the main branch and released package.
- AMD backend now matches NVIDIA-style cached metric sampling and `GPU.realtime()` bypass behavior
- README quick start moved earlier in the document
- `utilization_percent` semantics documented as vendor-reported top-level activity, not SM/CU occupancy

### Compatibility and scope

- The 1.0 Python API (`count`, `gpus`, `gpu`, `GPU.info`, `GPU.metrics`, and
  `GPU.realtime`) remains available. Core installation has no required vendor dependency.
- New structured agent commands return 0 PASS, 1 WARN, 2 FAIL, 3 INCONCLUSIVE,
  and 64 for invalid input. Overview/doctor/legacy bandwidth retain their existing
  exit behavior. A nonzero diagnostic result can be a successfully interpreted report.
- SDKs, drivers and compute frameworks are installed separately. Adapter availability
  does not imply certification of every card model; see the compatibility matrix.
- Active probes require explicit execution. A passing check applies to that workload;
  no universal sustained baseline or whole-device health guarantee is provided.
- The separate `feat/agent-preflight-cli` proposal is not part of this release.
  Minimum GPU/free-memory admission checks and `--require-idle` are not advertised.

## [1.0.0] - 2026-02-25

### Added

- New stable API: `count()`, `gpus()`, `gpu(index)`
- New `GPU.info()` and `GPU.metrics()` contract
- New public models: `GPUInfo`, `GPUMetrics`
- New backend architecture under `omnismi.backends`
- Unit normalization utilities under `omnismi.normalize`
- Local parity validation module: `omnismi.validation.parity`
- New documentation set under `docs/`
- New contributor and agent guidelines

### Changed

- Project version raised to `1.0.0`
- Optional NVIDIA dependency moved to `nvidia-ml-py`
- README rewritten as a short usage-oriented guide

### Removed

- Legacy 0.x API (`detect_gpus`, `GPUDevice`, `get_gpu`, `list_gpus`)
- CLI commands and runtime installer flows
- Legacy core/vendor structure and detection/installer modules
