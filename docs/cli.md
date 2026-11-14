# CLI

Install Omnismi 2.0.0 using the [quickstart](quickstart.md).
`python -m omnismi` and the `omnismi` console command invoke the same CLI.
The small Python API remains available independently of the command-line tools.
Run `omnismi --help` for the task-oriented command map and `omnismi --version`
to confirm the installed release. Agents should also read the
[agent integration guide](agents.md) before automating reports.

## Command map

| Need | Command | Default interface |
|---|---|---|
| See what the current process can use | `omnismi` | Human table |
| Explain missing devices or partial metrics | `omnismi doctor` | Human findings and next steps |
| Interpret an error or captured evidence | `omnismi decode`, `omnismi diagnose --input` | Structured JSON |
| Collect current hardware evidence | `omnismi diagnose --collect hardware` | Structured JSON |
| Compare performance with a recorded baseline | `omnismi perf-doctor` | Structured JSON |
| Discover topology and affinity | `omnismi topology` | Structured JSON |
| Run an explicit bounded workload | `omnismi bench matmul`, `omnismi bench suite` | Structured JSON |
| Compare inventory with a curated profile | `omnismi validate-spec --profile …` | Human table |

The bare command is intentionally the fastest human entry point. Add `-o json`
for overview automation, or use a structured report command when the task needs
an explicit verdict, evidence, sources, and limitations.

## Discovery and visibility

```bash
omnismi
omnismi --wide
omnismi --vendor nvidia -o json
omnismi doctor --verbose -o json
omnismi validate-spec --profile h100-pcie-80gb -o json
```

The default overview is a human-readable table, including on redirected stdout.
Use `-o json` or `-o yaml` explicitly for automation. `--wide`, `--watch`, `--color`
and `--no-color` control presentation. Common selection accepts `--vendor`, one or
more global `--device` indexes, or `--all-devices`.

`doctor` explains dependency, enumeration and visibility mismatches. `validate-spec`
compares discovered devices with a named curated profile. Missing devices and
unavailable metrics remain explicit; discovery alone does not establish health.
These existing commands retain their older exit behavior, so inspect structured
report verdicts rather than relying only on process success.

## Structured report commands

| Command | Purpose | Detailed guide |
|---|---|---|
| `decode` | Explain one vendor/namespace/error code offline | [Diagnostics](v2/diagnostics.md) |
| `diagnose --input` | Normalize captured logs, counters or events | [Diagnostics](v2/diagnostics.md) |
| `diagnose --collect hardware` | Collect bounded kernel/management/RAS/ECC evidence | [Diagnostics](v2/diagnostics.md) |
| `diagnose --self-test --vendor …` | Explicit bounded correctness checks | [Diagnostics](v2/diagnostics.md) |
| `perf-doctor` | Measure, save, build baselines and compare expected percentages | [Performance](v2/perf-doctor.md) |
| `topology` | Discover PCI/NUMA/NIC locality, vendor matrices and constrained affinity | [Topology](v2/topology-affinity.md) |
| `bench matmul` / `bench suite` | Explicit bounded compute or sequential probe suite | [Bench](bench.md) |
| `sail-build` | Compile the optional native PPU workload on its SDK host | [PPU](v2/alibaba-ppu.md) |
| `cndev-build` | Compile the optional MLU management collector on its SDK host | [MLU](v2/cambricon.md) |

New report commands emit JSON with `schema_version`, `report_type`, `status`,
`scope`, `data`, `evidence`, `sources` and `limitations`. Verdict exits are 0 PASS,
1 WARN, 2 FAIL, 3 INCONCLUSIVE, 64 invalid invocation/input. Successful baseline
construction and SDK compilation return 0. For codes 0–3, retain the JSON even
when the process exit is nonzero. The [quickstart](quickstart.md) includes checked
examples and their expected results.

## Choosing a device

Overview, doctor, validate-spec and legacy `bench bandwidth` use Omnismi's global
management indexes. Active `diagnose --self-test`, `perf-doctor --run`, `bench matmul`
and `bench suite` use the selected compute runtime's local index. Container masks
and partitions can make those indexes differ. Identity is retained in each report;
do not join tools by ordinal alone.

Live topology and SDK compilation require Linux. Offline interpretation and
performance comparison need neither hardware nor a runtime network connection.
PPU/MLU SDK compilation and actual card behavior still need target-host validation.
See [compatibility](compatibility.md) for evidence rather than treating software CI
as hardware certification.

## Agent admission commands (source checkout)

These commands are additive to the 2.0 CLI and are available from this source
checkout for the next release. They are absent from the published 2.0.0 package.
Running `omnismi` without arguments still shows the human-readable overview.

```bash
omnismi preflight --vendor nvidia --min-gpus 1 --min-free-gib 8
omnismi preflight --vendor amd --min-gpus 1
omnismi inventory
omnismi metrics --human
omnismi version
omnismi --version
```

`preflight` takes a one-shot inventory and realtime metrics snapshot, then applies
the requested vendor, GPU-count, and per-device free-memory requirements.
`--vendor` prevents a mixed host from satisfying a vendor-specific count with
other accelerators. A requested free-memory threshold fails with
`free_memory_unknown` when the evidence is unavailable; it never silently passes.
`inventory` and `metrics` return snapshots without threshold gates. They do not
start workloads. Both the console script and `python -m omnismi` support these
commands.

### Admission exit codes

| Code | Meaning |
|---|---|
| 0 | Admission requirements met, or a nonempty snapshot |
| 1 | Usage error, including invalid threshold arguments |
| 2 | No visible accelerators |
| 3 | GPU-count/free-memory threshold failure, or a requested threshold cannot be evaluated |
| 10 | Backend error |

These codes apply to `preflight`, `inventory`, and `metrics`. The structured 2.0
diagnostic commands above retain their verdict exit codes. `version`, `--version`,
and help exit 0. Admission usage errors write stderr without JSON on stdout.
Counts and memory thresholds must be non-negative; GiB values must be finite and
convertible to bytes. If both free-memory flags are supplied, the stricter applies.

### Admission JSON snapshots

The three snapshot commands share `schema_version`, `command`, `ok`, `exit_code`,
`ts_ns` (Unix time in nanoseconds), `summary`, `devices`, `warnings`, and `failures`,
including empty inventories and backend errors. This admission snapshot schema is
separate from the structured 2.0 diagnostic reports described above.

`summary` contains `gpu_count`, `vendors`, `all_free_bytes_min`, and `busy_gpu_count`.
Unknown free memory and the unavailable busy count are `null`. `--human` adds a
one-line summary to stderr while preserving JSON on stdout.

### Admission visibility and limits

Admission snapshots apply visibility controls only to the applicable vendor:
NVIDIA uses `CUDA_VISIBLE_DEVICES`; AMD uses `ROCR_VISIBLE_DEVICES`,
`HIP_VISIBLE_DEVICES`, and `GPU_DEVICE_ORDINAL`. Other vendors remain unfiltered
by these variables. `--all-devices` ignores all supported filters.

NVIDIA accepts integer management indexes, full UUIDs, and unique `GPU-` UUID
prefixes with case-insensitive matching. AMD's ROCR control accepts indexes and
UUIDs; HIP and `GPU_DEVICE_ORDINAL` accept indexes. Multiple active AMD controls
are intersected conservatively and produce a visibility warning. Bare suffixes,
ambiguous prefixes, invalid identifiers, and duplicates cannot inflate the count.
The first invalid or repeated identifier stops that control's list. An empty value
selects no devices for that vendor. For example, CUDA `0,2,-1,1` selects NVIDIA
devices 0 and 2, remapped to logical indexes 0 and 1.

See NVIDIA's [CUDA environment variable reference](https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/environment-variables.html)
and AMD's [HIP isolation variables](https://rocm.docs.amd.com/projects/HIP/en/latest/reference/env_variables.html#gpu-isolation-variables).
The snapshot includes `visibility.enforcement = runtime_hint_only`: these
variables are not proof of cgroup/device isolation, and management indexes can
differ from container or compute-runtime indexes. Retain UUID identity when
comparing reports.

`processes` and `topology` are reserved fields in admission snapshots.
`--require-idle` warns that it is not enforced; it must not be used as proof that a
device is idle. `--topology` warns that it is omitted; use the existing `topology`
command for a topology report. Admission snapshots use one-shot `GPU.realtime()`
reads and do not leave a sampler running.

## Workload execution

Management and offline commands do not automatically run benchmarks or modify
hardware settings. Active commands require an explicit execution choice, such as
`--self-test`, `--run` or `bench suite`. Read the [bench guide](bench.md) for memory,
timeout, correctness and expected-performance boundaries.
