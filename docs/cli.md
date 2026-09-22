# CLI

Install the 2.0 development preview using the [quickstart](quickstart.md).
`python -m omnismi` and the `omnismi` console command invoke the same CLI.
The small Python API remains available independently of the command-line tools.

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

## Structured 2.0 commands

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

## Workload execution

Management and offline commands do not automatically run benchmarks or modify
hardware settings. Active commands require an explicit execution choice, such as
`--self-test`, `--run` or `bench suite`. Read the [bench guide](bench.md) for memory,
timeout, correctness and expected-performance boundaries.
