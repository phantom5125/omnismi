# Quickstart

[中文上手指南](quickstart.zh-CN.md)

Start with an offline result on any Linux or macOS laptop. Add a vendor runtime
only when you move to a hardware host. Python 3.9+ is required; Python 3.12 is a
tested starting point. Linux is required for live sysfs topology and SDK builds.

## Install the 2.0 preview

The [PyPI release](https://pypi.org/project/omnismi/) is currently 1.0.0 and does
not include the preview commands below. Use this source branch:

```bash
git clone --branch codex/v2-runtime-completion --single-branch https://github.com/phantom5125/omnismi.git
cd omnismi
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

If you already cloned this branch, start at the virtual-environment step. All
relative file paths below are from the repository root. The core package has no
mandatory vendor dependencies. The development package version is still 1.0.0;
check command availability rather than using that number to identify the preview:

<!-- quickstart-smoke: help -->
```bash
python -m omnismi decode --help
```

For only the released Python telemetry API, install `omnismi`, `omnismi[nvidia]`
or `omnismi[amd]` from PyPI in a separate environment. See the [API](api.md).

## Interpret an error without hardware

<!-- quickstart-smoke: decode -->
```bash
python -m omnismi decode --vendor nvidia --namespace xid --code 48
```

The result is JSON. For this known error, expect:

- `status`: `FAIL`, describing the severity of the supplied event.
- `data.findings`: normalized interpretation and next checks.
- `sources`: the maintained vendor-document references used for the rule.
- `scope.current_hardware_health`: `INCONCLUSIVE`.

The command exits **2** because the event is an error. It did execute successfully;
no GPU, network request or LLM was used. This output does not establish that your
machine has an ECC fault.

Try the included synthetic log:

<!-- quickstart-smoke: log -->
```bash
python -m omnismi diagnose --input examples/diagnostics/xid48.log
```

Expected: `FAIL`, exit 2, with the supplied PCI identity in the evidence. Replace
the fixture path with your own captured log when ready. Unknown codes are explicit:

<!-- quickstart-smoke: unknown -->
```bash
python -m omnismi decode --vendor nvidia --namespace xid --code 999999
```

Expected: `INCONCLUSIVE`, exit 3. See [diagnostics](v2/diagnostics.md) for AMD RAS,
PPU generation selection, normalized event JSON and source coverage.

## Try the performance comparison

<!-- quickstart-smoke: performance -->
```bash
python -m omnismi perf-doctor --input examples/performance/synthetic-measurement.json --baseline examples/performance/synthetic-baseline.json
```

Expected: **80%** of expected sustained performance and **40%** of theoretical
peak, `WARN`, exit **1**, under this fixture's explicit policy. These are synthetic
arithmetic inputs, not measured card performance or a recommended threshold.
See [perf-doctor](v2/perf-doctor.md) to capture real runs, record conditions and
create a reproducible baseline.

## Connect a hardware host

Driver/SDK installations are separate from Omnismi. Install one matching backend
from this checkout, then inspect the read-only management view:

| Vendor | Prerequisites | Setup / query |
|---|---|---|
| NVIDIA | Working NVIDIA driver | `python -m pip install '.[nvidia]'`, then `omnismi --vendor nvidia -o json` |
| AMD | Matching ROCm/AMD SMI installation | `python -m pip install '.[amd]'`, then `omnismi --vendor amd -o json` |
| Google TPU | Supported TPU VM and LibTPU environment | `python -m pip install '.[tpu]'`, then `omnismi --vendor google -o json` |
| Alibaba PPU | SAIL SDK and `ppu-smi` | Follow [PPU setup](v2/alibaba-ppu.md), then `omnismi --vendor alibaba -o json` |
| Cambricon MLU | Installed CNDEV headers/library and C compiler | Follow [MLU setup](v2/cambricon.md), then `omnismi --vendor cambricon -o json` |

`omnismi doctor` explains enumeration, dependency and visibility issues. For live
Linux locality, use `omnismi topology`; add `--collect-vendor nvidia` or
`--collect-vendor alibaba` when that management tool is installed. See the
[compatibility matrix](compatibility.md) before interpreting a supported adapter
as a hardware-verified configuration.

## Explicitly run a bounded workload

Management telemetry does not require PyTorch. Active NVIDIA/AMD probes require a
matching torch compute runtime; MLU uses torch_mlu; PPU uses the SDK-compiled HGGC
probe from [PPU setup](v2/alibaba-ppu.md). Omnismi does not install these runtimes.

Once the runtime can see the intended device, this command executes a self-test,
copy/triad bandwidth and FP32 matrix multiplication in sequence:

```bash
omnismi bench suite --vendor nvidia --device 0 --memory-mib 64 --timeout 90
```

Choose the actual vendor. `--device` here is a **compute-runtime index**, which
may differ from the overview's global index. The suite shares one deadline and
stops if a step cannot pass. Its PASS covers numerical correctness of the selected
operations; use `perf-doctor` and a matching baseline to judge performance.

## Handle reports in scripts and agents

New commands (`decode`, `diagnose`, `perf-doctor`, `topology`, `bench matmul/suite`)
return JSON and use these exit codes:

| Exit | Meaning |
|---|---|
| 0 | PASS, or successful baseline construction |
| 1 | WARN |
| 2 | FAIL in the supplied evidence or executed checks |
| 3 | INCONCLUSIVE: missing evidence, unsupported input, runtime or baseline |
| 64 | Invalid invocation/input; inspect stderr |

Retain stdout for codes 0–3. A generic `check=True`, shell `set -e`, or `&&` chain
would otherwise treat the intentional demo verdicts as execution failures.
Overview/doctor/legacy `bench bandwidth` keep their older exit behavior.

For Python agents, call the library directly and keep the structured report:

```python
from omnismi.diagnostics import decode_error

report = decode_error("nvidia", "xid", 48)
print(report["status"])
print(report["data"]["findings"])
```

## Common first-run issues

| Symptom | Next step |
|---|---|
| `omnismi` is not found | Activate the venv, or use `python -m omnismi` with the interpreter where it was installed. |
| `decode` is unrecognized | You likely installed PyPI 1.0.0 or another checkout; install this preview branch in the active venv. |
| Zero devices or null metrics | Run `omnismi doctor`; check the selected backend dependency, driver access and container visibility. Zero is not a health verdict. |
| `dmesg`/sysfs permission denied | Use an authorized captured log with `diagnose --input`; do not assume empty evidence means a healthy device. |
| `SAIL_native_probe_not_installed` | Build with `omnismi sail-build` on the SDK host and set `OMNISMI_SAIL_PROBE`. |
| Cambricon collector unavailable | Build with `omnismi cndev-build` and set `OMNISMI_CNDEV_PROBE`; see the MLU guide. |
| A performance run is INCONCLUSIVE | Inspect its reason: missing runtime, conditions or baseline have different remedies. A successful sample can still be saved without a comparison verdict. |

The offline examples on this page and the Chinese guide are executed by CI
against an installed wheel. Physical-card workflows need separate hardware evidence.
