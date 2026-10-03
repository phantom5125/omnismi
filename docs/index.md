# Omnismi

<p align="center">
  <img src="assets/OMNIsmi.svg" alt="Omnismi logo" width="300" />
</p>

Omnismi is a cross-vendor accelerator tool for people and AI agents. Inspect
hardware, explain error evidence, compare performance and discover locality
through shared commands and structured reports. The Python API is available
for applications that prefer an in-process integration.

## Start here

- [Quickstart](quickstart.md): package installation, no-GPU examples and expected results.
- [中文上手指南](quickstart.zh-CN.md): 安装、离线诊断、性能百分比和常见问题。
- [CLI](cli.md): select the right command and interpret its output.
- [Product direction](why-omnismi.md): portable workflows and framework boundaries.
- [Compatibility](compatibility.md): distinguish adapter availability from validated hardware.
- [2.0 delivery status](v2/STATUS.md): implemented workflows and remaining evidence.

Install version 2.0.0 from [PyPI](https://pypi.org/project/omnismi/2.0.0/) with
`python -m pip install --upgrade 'omnismi==2.0.0'`. The same distributions and
checksums are available on [GitHub](https://github.com/phantom5125/omnismi/releases/tag/release-2.0.0).

## Use the tool

```bash
omnismi
omnismi --vendor nvidia -o json
omnismi doctor --verbose -o json
```

The first command shows a terminal overview. Explicit JSON output lets scripts
and agents read normalized reports. Additional commands cover
[diagnostics](v2/diagnostics.md), [performance](v2/perf-doctor.md) and
[topology](v2/topology-affinity.md). The [2.1 self-test](v2.1/hardware-selftest.md)
is a development preview; its new commands require that branch's installation.

## Integrate through Python

```python
import omnismi as omi

print(omi.count())
for device in omi.gpus():
    print(device.info())
    print(device.metrics())
```

Core installs without vendor dependencies. Add the matching backend when reading
real hardware: NVIDIA via NVML, AMD via AMD SMI, Google TPU via LibTPU, PPU via
SAIL PPU-SMI, or MLU via the SDK-compiled CNDEV collector. See [API](api.md) for
`gpu(index)`, normalized units, caching and `GPU.realtime()`.

## Agent workflows

Use [diagnostics](v2/diagnostics.md) for source-backed interpretation,
[perf-doctor](v2/perf-doctor.md) for expected percentages,
[topology](v2/topology-affinity.md) for locality, and [bench](bench.md) for explicit
bounded workloads. The [PPU](v2/alibaba-ppu.md) and [MLU](v2/cambricon.md) guides cover
SDK setup. Reports preserve missing evidence and unavailable metrics instead of
turning incomplete observations into a healthy-device verdict.
