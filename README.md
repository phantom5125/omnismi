# Omnismi

<p align="center">
  <img src="docs/assets/OMNIsmi.svg" alt="Omnismi logo" width="320" />
</p>

[![CI](https://github.com/phantom5125/omnismi/actions/workflows/v2-checks.yml/badge.svg?branch=main&event=push)](https://github.com/phantom5125/omnismi/actions/workflows/v2-checks.yml?query=branch%3Amain)
[![PyPI release](https://img.shields.io/pypi/v/omnismi?label=PyPI%20release)](https://pypi.org/project/omnismi/)
[![Python](https://img.shields.io/badge/Python-%3E%3D3.9-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Agent-ready accelerator observability, diagnostics, and validation — through one CLI and a small Python API.**

Omnismi helps humans and AI agents answer practical questions before and during
accelerator work: **Which devices can this process actually use? What do the
current metrics and errors mean? Can the selected device execute a bounded,
correct workload?** It provides one normalized workflow across NVIDIA, AMD,
Google TPU, Alibaba PPU, and Cambricon MLU without hiding missing evidence or
runtime constraints.

[Quickstart](docs/quickstart.md) · [中文上手指南](docs/quickstart.zh-CN.md) ·
[CLI guide](docs/cli.md) · [Agent guide](docs/agents.md) ·
[Hardware compatibility](docs/compatibility.md)

## What you can do

| Goal | Command | Result |
|---|---|---|
| See the current runtime's devices | `omnismi` | Concise human table with inventory and live telemetry |
| Understand missing devices or metrics | `omnismi doctor` | Plain-language findings, likely causes, and next steps |
| Explain a vendor error offline | `omnismi decode --vendor nvidia --namespace xid --code 48` | Source-backed findings and explicit uncertainty |
| Diagnose captured evidence | `omnismi diagnose --input events.log` | Versioned JSON with evidence and limitations |
| Compare a run with your baseline | `omnismi perf-doctor --input run.json --baseline baseline.json` | Expected-sustained and theoretical-peak percentages |
| Inspect device locality | `omnismi topology` | PCI, NUMA, NIC, and supported vendor-link relationships |
| Check execution explicitly | `omnismi bench suite --vendor nvidia --device 0 --memory-mib 64` | Bounded correctness and workload results |

Management queries and offline diagnosis never launch a benchmark. Active
workloads require an explicit command and declare their memory and time bounds.

## Start in 30 seconds, with or without a GPU

Install the core package on Linux or macOS with Python 3.9+:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade 'omnismi==2.0.0'
```

Decode a recorded NVIDIA error without a GPU, driver, LLM, or runtime network
request:

<!-- quickstart-smoke: decode -->
```bash
python -m omnismi decode --vendor nvidia --namespace xid --code 48
```

The JSON report has `"status":"FAIL"` because the **supplied event** is an
error, and exits **2**. This is a successful offline interpretation, not a claim
that your current GPU is faulty. Continue with the [quickstart](docs/quickstart.md)
for captured logs and an 80%-of-expected performance example.

On a hardware host, install the matching adapter and inspect the current runtime:

| Hardware | Setup | Read-only query |
|---|---|---|
| NVIDIA | Working driver; `python -m pip install 'omnismi[nvidia]==2.0.0'` | `omnismi --vendor nvidia` |
| AMD | Matching ROCm/AMD SMI stack; `python -m pip install 'omnismi[amd]==2.0.0'` | `omnismi --vendor amd` |
| Google TPU | TPU VM; `python -m pip install 'omnismi[tpu]==2.0.0'` | `omnismi --vendor google` |
| Alibaba PPU | SAIL SDK with `ppu-smi` on PATH; [setup](docs/v2/alibaba-ppu.md) | `omnismi --vendor alibaba` |
| Cambricon MLU | Build the collector against installed CNDEV; [setup](docs/v2/cambricon.md) | `omnismi --vendor cambricon` |

Add `-o json` to overview commands for automation. Use `omnismi doctor` when
device counts, dependencies, permissions, or container visibility look wrong.

## Designed for agents and humans

For humans, the bare command is a readable summary, `--wide` adds detail, and
`doctor` ends in actionable next steps. `omnismi --help` provides a complete
command map rather than requiring knowledge of the Python package.

For agents, structured reports preserve verdicts, scope, evidence, sources, and
limitations. The `decode`, `diagnose`, `perf-doctor`, `topology`, and
`bench matmul/suite` commands use these exits:

| Exit | Meaning |
|---|---|
| 0 | PASS or successful baseline construction |
| 1 | WARN |
| 2 | FAIL in the supplied evidence or executed checks |
| 3 | INCONCLUSIVE: evidence, runtime, support, or baseline is insufficient |
| 64 | Invalid invocation or input; inspect stderr |

Retain stdout for exits 0–3; do not use `check=True` or `set -e` in a way that
throws away a valid WARN/FAIL report. Overview, `doctor`, `validate-spec`, and
legacy `bench bandwidth` retain their older exit behavior. See the
[agent guide](docs/agents.md) for a safe subprocess wrapper and report schemas.

## Embed the Python API when you need it

The CLI is the operational interface; the stable Python API remains available
for in-process inventory and metrics:

```python
import omnismi as omi

print(omi.count())
for device in omi.gpus():
    print(device.info())
    print(device.metrics())
```

Units are normalized to bytes, percent, Celsius, Watts, and MHz. Unavailable
metrics stay `None`. Core has no mandatory vendor dependency. See the
[API guide](docs/api.md) for selection, caching, and `GPU.realtime()`.

## Know what a result proves

- A green CI badge validates software and synthetic protocols, not every card.
- NVIDIA H20 and AMD MI300X have earlier telemetry evidence; new 2.0 paths still
  need target-host evidence.
- Google TPU is experimental. Alibaba PPU and Cambricon MLU have fixture and
  synthetic native-runtime tests; real SDK/card validation is pending.
- A self-test PASS covers only the executed checks, not whole-device health.
- Performance comparisons require your recorded conditions and a comparable
  baseline; Omnismi does not invent universal thresholds.

See [compatibility](docs/compatibility.md) and the
[2.0 delivery status](docs/v2/STATUS.md) for precise evidence boundaries.

## Agent admission checks (source checkout)

The next release adds `omnismi preflight --min-gpus 1 --min-free-gib 8`,
`omnismi inventory`, and `omnismi metrics` as JSON snapshots, plus
`omnismi version`. Install this source checkout to use them; the published
2.0.0 package does not include them. The default overview and existing diagnostics,
topology, and benchmark commands remain available.
See the [CLI guide](docs/cli.md#agent-admission-commands-source-checkout) for the
admission commands' exit codes and visibility rules.

## What Omnismi is not

Omnismi is not a monitoring daemon, a full profiler, or a replacement for vendor
management tools. It does not install drivers, SDKs, or PyTorch, change hardware
settings, or turn missing evidence into a healthy-device verdict.

## Development

```bash
python -m pip install -e '.[dev,docs]' build twine
python -m pytest -q
python -m mkdocs build --strict
python -m build
python -m twine check dist/*
```

See [Contributing](CONTRIBUTING.md) for installed-wheel checks and hardware
evidence, [Why Omnismi](docs/why-omnismi.md) for the design, and the
[MIT license](LICENSE).
