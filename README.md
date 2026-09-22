# Omnismi

<p align="center">
  <img src="docs/assets/OMNIsmi.svg" alt="Omnismi logo" width="320" />
</p>

[![Preview CI](https://github.com/phantom5125/omnismi/actions/workflows/v2-checks.yml/badge.svg?branch=codex%2Fv2-runtime-completion&event=push)](https://github.com/phantom5125/omnismi/actions/workflows/v2-checks.yml?query=branch%3Acodex%2Fv2-runtime-completion)
[![PyPI release](https://img.shields.io/pypi/v/omnismi?label=PyPI%20release)](https://pypi.org/project/omnismi/)
[![Python](https://img.shields.io/badge/Python-%3E%3D3.9-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![2.0 preview](https://img.shields.io/badge/2.0-development%20preview-orange)](docs/v2/STATUS.md)

Cross-vendor accelerator observability and structured diagnostics for Python apps
and AI agents. Read normalized metrics, explain error evidence offline, compare
performance with recorded baselines, and discover topology and affinity.

**Start here:** [Quickstart](docs/quickstart.md) · [中文上手指南](docs/quickstart.zh-CN.md) ·
[Hardware compatibility](docs/compatibility.md) · [2.0 delivery status](docs/v2/STATUS.md)

## Choose the version

| Goal | Install | Available workflows |
|---|---|---|
| Released Python API | `python -m pip install omnismi` | The PyPI 1.0.0 API; add `nvidia` or `amd` extras for telemetry |
| Try the 2.0 work in this repository | Clone the preview branch below and install `.` | CLI, offline diagnosis, perf-doctor, topology, PPU and Cambricon adapters |

The PyPI badge describes the released package. Preview CI describes the explicit
`codex/v2-runtime-completion` branch. The preview has **not** been published as 2.0;
its package version is still 1.0.0. A PyPI install does not contain these new commands.

## First result without a GPU

On Linux or macOS with Git and Python 3.9+:

```bash
git clone --branch codex/v2-runtime-completion --single-branch https://github.com/phantom5125/omnismi.git
cd omnismi
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Already in this checkout? Create/activate the virtual environment and install `.`;
skip the clone. Core has no mandatory vendor dependency. Python 3.12 is a tested
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

From the preview checkout, choose the dependency for the hardware you already have:

| Hardware | Setup | Read-only query |
|---|---|---|
| NVIDIA | `python -m pip install '.[nvidia]'`; working driver | `omnismi --vendor nvidia -o json` |
| AMD | `python -m pip install '.[amd]'`; matching ROCm/SMI stack | `omnismi --vendor amd -o json` |
| Google TPU | `python -m pip install '.[tpu]'` on a TPU VM | `omnismi --vendor google -o json` |
| Alibaba PPU | SAIL SDK with `ppu-smi` on PATH; [setup](docs/v2/alibaba-ppu.md) | `omnismi --vendor alibaba -o json` |
| Cambricon MLU | Build the collector against installed CNDEV; [setup](docs/v2/cambricon.md) | `omnismi --vendor cambricon -o json` |

Omnismi does not install drivers, SDKs or PyTorch. `.[all]` includes NVIDIA, AMD and
TPU Python dependencies; PPU/MLU still require their vendor setup. Missing devices
or permissions are explained by `omnismi doctor`; unavailable metrics stay null.

The small Python API works in both the released package and this preview:

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
