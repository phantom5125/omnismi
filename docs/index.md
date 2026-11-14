# Omnismi

<p align="center">
  <img src="assets/OMNIsmi.svg" alt="Omnismi logo" width="300" />
</p>

**Agent-ready accelerator observability, diagnostics, and validation — through
one CLI and a small Python API.**

Omnismi helps humans and AI agents determine which accelerators the current
process can use, interpret metrics and recorded errors, inspect locality, and
run explicitly bounded correctness and performance checks. It normalizes common
workflows across vendors while preserving unavailable metrics, missing evidence,
and runtime limitations.

## Choose your task

| I want to… | Start here |
|---|---|
| See visible devices and live telemetry | Run `omnismi`, then read the [CLI guide](cli.md) |
| Explain missing devices or partial metrics | Run `omnismi doctor` |
| Explain an error or captured log without hardware | Follow the [quickstart](quickstart.md) |
| Integrate structured reports into an agent | Read the [agent guide](agents.md) |
| Compare real performance with my own baseline | Use [perf-doctor](v2/perf-doctor.md) |
| Inspect PCI/NUMA/NIC locality and vendor links | Use [topology](v2/topology-affinity.md) |
| Run an explicit bounded accelerator check | Read [Bench](bench.md) |
| Embed inventory and metrics in a Python app | Read the [API guide](api.md) |

## Install and get a first result

Install version 2.0.0 from [PyPI](https://pypi.org/project/omnismi/2.0.0/):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade 'omnismi==2.0.0'
python -m omnismi decode --vendor nvidia --namespace xid --code 48
```

The last command interprets the supplied error offline and exits 2 with a FAIL
report. It does not inspect or make a health claim about the current machine.
The [quickstart](quickstart.md) and [中文上手指南](quickstart.zh-CN.md) include
checked examples, expected verdicts, and exit-code handling.

On an accelerator host, add the matching backend and run the human overview:

```bash
python -m pip install 'omnismi[nvidia]==2.0.0'
omnismi
```

NVIDIA uses NVML, AMD uses AMD SMI, Google TPU uses LibTPU, Alibaba PPU uses the
SAIL PPU-SMI interface, and Cambricon MLU uses an SDK-compiled CNDEV collector.
Omnismi does not install drivers, SDKs, or compute frameworks.

## One operational tool, two interfaces

The CLI is the operational interface for humans and agents. Use `-o json` for
overview automation, or use the structured diagnostic, performance, topology,
and active bench commands for versioned reports. The [agent guide](agents.md)
explains verdict exits, safe subprocess handling, and the difference between
read-only inspection and explicit workloads.

For in-process application integration, the stable Python API remains small:

```python
import omnismi as omi

print(omi.count())
for device in omi.gpus():
    print(device.info())
    print(device.metrics())
```

Units are bytes, percent, Celsius, Watts, and MHz. Unavailable metrics remain
`None`; incomplete observations are not converted into a healthy-device verdict.

## Evidence before claims

Adapter availability is not hardware certification. Check the
[compatibility matrix](compatibility.md) for real-device evidence and the
[2.0 delivery status](v2/STATUS.md) for workload, SDK, and topology boundaries.
Omnismi is not a monitoring daemon, a full profiler, or a replacement for
vendor-native management tools.
