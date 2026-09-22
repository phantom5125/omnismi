# Omnismi

<p align="center">
  <img src="assets/OMNIsmi.svg" alt="Omnismi logo" width="300" />
</p>

Read accelerator information through one small Python API. In the 2.0 preview,
explain error evidence offline, compare measured performance with recorded
baselines, and discover topology and affinity through structured agent commands.

## Start here

- [Quickstart](quickstart.md): source installation, no-GPU examples and expected results.
- [中文上手指南](quickstart.zh-CN.md): 安装、离线诊断、性能百分比和常见问题。
- [CLI](cli.md): select the right command and interpret its output.
- [Compatibility](compatibility.md): distinguish adapter availability from validated hardware.
- [2.0 delivery status](v2/STATUS.md): implemented workflows and remaining evidence.

The PyPI release is 1.0.0. Preview commands require the source branch described in
the quickstart; they have not been published as a 2.0 package.

## Python API

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
