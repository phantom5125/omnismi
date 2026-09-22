# Alibaba / T-Head SAIL PPU

The adapter is registered as vendor `alibaba` and uses documented SAIL v2.1.1
PPU-SMI queries. It is fixture-tested; no PPU model is marked hardware-verified.
Install vendor tooling independently and put `ppu-smi` on PATH.

```bash
omnismi --vendor alibaba --output json
omnismi diagnose --collect hardware --vendor alibaba
omnismi decode --vendor alibaba --namespace xid-ppu001 --code 2706
omnismi decode --vendor alibaba --namespace xid-ppu0015 --code 4997
omnismi topology --collect-vendor alibaba
```

Inventory/memory use CSV fields index/name/UUID/PCI/driver/memory.total/memory.used.
Telemetry uses documented `ppu-smi -q` sections: utilization (Ppu, %), current
temperature (C), power draw (W), CU and memory clocks (MHz). UUID/PCI must match
between inventory and telemetry. Ambiguous IDs, unknown units and invalid ranges
are rejected. Memory remains available when optional telemetry is unavailable;
passive hardware reports retain the telemetry error reason and ECC counters.

MiB is converted to bytes. Missing fields stay null and zero stays zero. Sampling
is cached for 0.5 seconds on demand, with a 5-second / 1-MiB budget per command,
no shell and no background polling. The hardware-diagnosis and live-topology
wrappers additionally enforce whole-operation deadlines.

PPU XID coverage contains all numeric rows in the reviewed PPU001 (68) and PPU0015
(87) tables. Reporting-client attribution is not proof that that block is defective.
Generation must be selected explicitly; codes are never borrowed from NVIDIA.
Four documented SRAM/DRAM correctable/uncorrectable counter rules preserve historical
volatile/aggregate scope. ICN matrices preserve path labels and bond counts without
claiming measured bandwidth or direct peer links.

Physical management visibility is not guaranteed runtime/MIG visibility. Native
HGML is accessed through the vendor's PPU-SMI boundary. Active probes use the native
HGGC runtime directly, with its own runtime-local device index. They do not select
PPUs through a generic CUDA or torch device ordinal.

## Native SAIL self-test and performance probes

On a Linux host with the matching SAIL SDK, activate the vendor's compiler and
runtime environment, then build Omnismi's bundled source:

```bash
mkdir -p bin
omnismi sail-build --output "$PWD/bin/omnismi-sail-probe"
export OMNISMI_SAIL_PROBE="$PWD/bin/omnismi-sail-probe"
omnismi diagnose --self-test --vendor alibaba --device 0 --memory-mib 64 --timeout 30
omnismi bench suite --vendor alibaba --device 0 --memory-mib 64 --timeout 90
omnismi perf-doctor --run bandwidth --vendor alibaba --context conditions.json --save-measurement ppu-copy.json
omnismi perf-doctor --run compute --vendor alibaba --context conditions.json --save-measurement ppu-matmul.json
```

`--compiler /path/to/hgcc` selects the installed compiler. By default both
`ppu_10` and `ppu_15` are compiled; repeat `--architecture` to select specific
supported targets. Builds are bounded by `--timeout` (default 120 seconds), return
source hashes, never overwrite an existing output and never run a workload.
The runtime also searches PATH for `omnismi-sail-probe` when the environment
variable is absent. A missing binary/SDK, invalid protocol, runtime error or timeout
is INCONCLUSIVE; no torch installation or SDK download happens automatically.

The worker allocates three FP32 buffers within the declared device-memory budget.
Copy and vector-add correctness use position-dependent patterns at four scales;
self-test also verifies matrix multiplication. Timed copy, vector add and tiled
16x16 FP32 matrix multiplication retain repeated synchronized host timings and
verify the final output. The compute probe is Omnismi's portable kernel, not a
vendor BLAS/tensor-core peak benchmark; its exact version remains in the baseline
signature. Small buffers may hit cache. See [performance](perf-doctor.md) for byte
and FLOP accounting, context fields and baseline construction.

Identity comes from `hggcGetDeviceProperties`, `hggcRuntimeGetVersion` and
`hggcDriverGetVersion`; raw runtime/driver version integers are preserved. Device
selection respects the installed runtime's `HGGC_VISIBLE_DEVICES` behavior.
Documented domain/bus/device properties do not include a PCI function, so the
report preserves a partial `pci_location` and does not invent a complete BDF or
join it to management inventory. Whole-device health remains INCONCLUSIVE even
when the selected correctness checks pass.

The host-control code is compiled and tested locally with a deliberately synthetic
runtime, including corruption and error paths. HGGC device compilation and real
PPU execution remain to be verified on the target SDK/card; no such result is
claimed from the CPU tests.

Primary references:

- [PPU-SMI v2.1.1 manual](https://developer.t-head.cn/docs_center/doc_detail/index.html?projectId=39&chapterId=221)
- [PPU001 XID table](https://developer.t-head.cn/docs_center/doc_detail/index.html?projectId=38&chapterId=182)
- [HGGC programming guide](https://developer.t-head.cn/docs_center/doc_detail/index.html?projectId=39&chapterId=196)
- [HGCC compiler guide](https://developer.t-head.cn/docs_center/doc_detail/index.html?projectId=39&chapterId=210)
- [Pinned official HGGC examples](https://github.com/t-head/hggc-samples/tree/ff1a055950ba70c308bf27357acf9bd4f7b61719)
- [PPU0015 XID table](https://developer.t-head.cn/docs_center/doc_detail/index.html?projectId=38&chapterId=183)

Source hashes/review dates are packaged in the offline catalog. No driver/SDK
installer or complete proprietary manual is bundled. Real-device parity, installed
SDK versions, runtime visibility and exact target card remain validation inputs.
