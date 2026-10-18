# Changelog

## [Unreleased]

## [1.1.0] - Unreleased

### Added

- Agent CLI commands: `omnismi preflight`, `inventory`, `metrics`, and `version`.
- Versioned JSON snapshots with timestamps, summaries, visibility mappings, and
  distinct exit codes for invalid arguments, empty inventory, failed thresholds,
  and backend errors.
- CUDA visibility filtering with logical index remapping, unique GPU UUID prefixes,
  and an explicit `--all-devices` override.
- CPU-only GitHub Actions checks for the CLI, visibility, and existing API tests.
- Experimental Google TPU backend backed by `libtpu.sdk.tpumonitoring`

### Fixed

- Reject negative preflight thresholds and non-finite or overflowing GiB values.
- Reject UUID suffixes and ambiguous prefixes; stop visibility at the first invalid
  or repeated device identifier instead of selecting later devices or double-counting.

### Changed

- AMD backend now matches NVIDIA-style cached metric sampling and `GPU.realtime()` bypass behavior
- README quick start moved earlier in the document
- `utilization_percent` semantics documented as vendor-reported top-level activity, not SM/CU occupancy

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
