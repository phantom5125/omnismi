# Changelog

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
