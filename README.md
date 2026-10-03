# Omnismi

<p align="center">
  <img src="docs/assets/OMNIsmi.svg" alt="Omnismi logo" width="320" />
</p>

[![CI](https://github.com/phantom5125/omnismi/actions/workflows/v2-checks.yml/badge.svg?branch=main&event=push)](https://github.com/phantom5125/omnismi/actions/workflows/v2-checks.yml?query=branch%3Amain)
[![PyPI release](https://img.shields.io/pypi/v/omnismi?label=PyPI%20release)](https://pypi.org/project/omnismi/)
[![Python](https://img.shields.io/badge/Python-%3E%3D3.9-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/phantom5125/omnismi)](https://github.com/phantom5125/omnismi/releases/latest)

**A cross-vendor accelerator tool for people and AI agents.** Inspect devices,
explain errors, check performance, discover topology and test correctness through
consistent commands and structured reports. Reuse your inspection and validation
workflows across supported hardware; Omnismi handles vendor-specific collection
and execution adapters. The Python API is an integration option.

Omnismi complements compute frameworks by focusing on hardware visibility,
readiness and diagnostic evidence. See [product direction and framework boundaries](docs/why-omnismi.md)
for what cross-hardware portability means and which capabilities are still planned.

**Start here:** [Quickstart](docs/quickstart.md) · [中文上手指南](docs/quickstart.zh-CN.md) ·
[Hardware compatibility](docs/compatibility.md) · [2.0 delivery status](docs/v2/STATUS.md)

**2.1 development preview:** this branch adds opt-in CPU-reference operator
self-tests, including independent topk checks and interleaved load testing,
plus an English-first [local dashboard](docs/v2.1/dashboard.md) with guided commands,
source-linked hardware module maps, and
RTX 5090 / B300 / MI355X / TPU v6e presets (real-card validation pending).
See the [2.1 guide and coverage limits](docs/v2.1/hardware-selftest.md).
For real cards, follow the [staged acceptance guide](docs/v2.1/hardware-acceptance.md)
with `omnismi self-test campaign` on an existing Pod, VM or local device.
This preview does not certify every physical unit; PPU SDC execution is pending.
The commands below still describe the published **2.0.0** release.

## Install 2.0.0

Version 2.0.0 includes the Python API, CLI, offline diagnosis, perf-doctor,
topology, and optional PPU and Cambricon adapters. See the [changelog](CHANGELOG.md)
for migration notes and the [release](https://github.com/phantom5125/omnismi/releases/tag/release-2.0.0)
for wheel and source downloads.

Version 2.0.0 is available on [PyPI](https://pypi.org/project/omnismi/2.0.0/).
The GitHub release provides the same wheel and source distribution with checksums.

## First result without a GPU

On Linux or macOS with Python 3.9+:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade 'omnismi==2.0.0'
```

From a source checkout, install `.` in the virtual environment instead.
Core has no mandatory vendor dependency. Python 3.12 is a tested
starting point; hardware collection and SDK builds target Linux.

<!-- quickstart-smoke: decode -->
```bash
python -m omnismi decode --vendor nvidia --namespace xid --code 48
```

Expected: JSON with `"status":"FAIL"` and source-backed findings for the supplied
error; exit code **2**. This is a successful interpretation of error evidence,
not a crash or proof that the current machine has faulty hardware. No GPU, driver,
LLM or runtime network access is needed. See the [quickstart](docs/quickstart.md)
for sample logs, an 80% performance comparison and exit-code handling.

## Read a real device

Choose the dependency for the hardware you already have:

| Hardware | Setup | Read-only query |
|---|---|---|
| NVIDIA | `python -m pip install 'omnismi[nvidia]==2.0.0'`; working driver | `omnismi --vendor nvidia -o json` |
| AMD | `python -m pip install 'omnismi[amd]==2.0.0'`; matching ROCm/SMI stack | `omnismi --vendor amd -o json` |
| Google TPU | `python -m pip install 'omnismi[tpu]==2.0.0'` on a TPU VM | `omnismi --vendor google -o json` |
| Alibaba PPU | SAIL SDK with `ppu-smi` on PATH; [setup](docs/v2/alibaba-ppu.md) | `omnismi --vendor alibaba -o json` |
| Cambricon MLU | Build the collector against installed CNDEV; [setup](docs/v2/cambricon.md) | `omnismi --vendor cambricon -o json` |

Omnismi does not install drivers, SDKs or PyTorch. `omnismi[all]` includes NVIDIA, AMD and
TPU Python dependencies; PPU/MLU still require their vendor setup. Missing devices
or permissions are explained by `omnismi doctor`; unavailable metrics stay null.

The small Python API remains compatible with 1.0:

```python
import omnismi as omi

print(omi.count())
for device in omi.gpus():
    print(device.info())
    print(device.metrics())
```

Units are bytes, percent, Celsius, Watts and MHz. See [API](docs/api.md) for
`gpu(index)`, caching and `GPU.realtime()`.

## Pick a workflow

| Need | Command | Guide |
|---|---|---|
| Explain a recorded error | `omnismi decode --vendor nvidia --namespace xid --code 48` | [Diagnostics](docs/v2/diagnostics.md) |
| Inspect current evidence | `omnismi diagnose --collect hardware` | [Collection and self-test](docs/v2/diagnostics.md) |
| Discover locality | `omnismi topology --collect-vendor nvidia` | [Topology and affinity](docs/v2/topology-affinity.md) |
| Compare with a baseline | `omnismi perf-doctor --input run.json --baseline baseline.json` | [Performance](docs/v2/perf-doctor.md) |
| Explicitly execute bounded checks | `omnismi bench suite --vendor nvidia --device 0 --memory-mib 64 --timeout 90` | [Bench](docs/bench.md) |

The suite allocates accelerator memory and runs workloads; use it only when you
intend to test the selected runtime device. It requires a compatible compute
runtime. A passing self-test covers the executed checks, not whole-device health.

## Validation status

| Adapter | Evidence |
|---|---|
| NVIDIA / AMD | Existing H20 / MI300X telemetry validation; new 2.0 paths still need target-host evidence |
| Google TPU | Experimental; user validation needed |
| Alibaba PPU / Cambricon MLU | Implemented, with fixture and synthetic native-runtime tests; real SDK/card validation pending |

CI checks Python regressions, native protocol stand-ins, built-wheel installation,
quickstart commands, package metadata and documentation. A green badge is software
validation, not accelerator certification. Full evidence is in the
[compatibility matrix](docs/compatibility.md) and [delivery status](docs/v2/STATUS.md).

## Development

```bash
python -m pip install -e '.[dev,docs]' build twine
python -m pytest -q
python -m mkdocs build --strict
python -m build
python -m twine check dist/*
```

See [Contributing](CONTRIBUTING.md) for installed-wheel checks and hardware evidence,
[Why Omnismi](docs/why-omnismi.md) for the design, and [MIT license](LICENSE).
