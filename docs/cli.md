# CLI

This page defines the Omnismi CLI surface. The main `omnismi` discovery command
and `omnismi doctor` are implemented today; richer benchmarking and
spec-validation layers remain planned as the CLI grows. The CLI is intended to
make Omnismi immediately useful in terminals, containers, and automation, while
keeping the Python API minimal.

## Design goals

- Make `omnismi` useful with zero extra explanation for first-time users.
- Provide a direct machine overview similar in spirit to `nvidia-smi`, but with
  a cleaner cross-vendor design.
- Keep structured output first-class for agents, CI, and orchestration.
- Work consistently on supported GPU hosts, GPU containers, and Kubernetes GPU pods.
- Reuse one coherent object model across discovery, diagnostics, and benchmarking.

## UX principles

- Discovery first: `omnismi` should answer "what hardware can I use right now?"
- Human-first main entry: the default command should optimize for a person reading
  a terminal, not for a machine parser.
- Modern default view: favor concise sections, clear status signals, and
  normalized units over legacy dense text dumps.
- Visual hierarchy matters: use clear blocks, separators, compact rows, and
  optional color so the screen feels like an operational dashboard rather than
  a raw debug dump.
- Cross-vendor wording: avoid vendor-specific jargon in the default view when a
  portable term exists.
- Honest degradation: when data is missing, say why instead of inventing values.
- Structured output parity: `table`, `json`, and `yaml` should all reflect the
  same underlying report object.
- Explicit structure for machines: scripts and agents should opt into
  `-o json` or `-o yaml` rather than relying on default stdout heuristics.

## Command layout

The planned top-level CLI should center on four user-facing workflows:

```bash
omnismi
omnismi doctor [flags]
omnismi bench <subcommand> [flags]
omnismi validate-spec [flags]
```

### `omnismi`

This is the primary discovery command and the fastest path for users who just
want a machine summary.

Main-entry rules:

- default output is always human-readable `table`
- do not auto-switch to `json` just because stdout is redirected
- keep the zero-flag experience useful on hosts, containers, and no-GPU environments
- favor a short, high-signal summary over a complete dump
- grow the experience with flags such as `--wide`, `--watch`, `--color`, and `-o`
- do not require a redundant `overview` subcommand for the main summary path

### `omnismi doctor`

Return a more explicit diagnostic report when discovery or metrics look wrong.

Expected use cases:

- a backend library imports but cannot enumerate devices
- metrics are partially unavailable
- Omnismi and the surrounding runtime appear to disagree about visibility

Recommended common flags:

- `--device INDEX`
- `--all-devices`
- `--vendor nvidia|amd|google`
- `-o, --output table|json|yaml`
- `--verbose`
- `--color auto|always|never`
- `--no-color`

### `omnismi bench`

Run portable accelerator probes. See [Bench](bench.md).

### `omnismi validate-spec`

Compare discovery output and benchmark results against an expected machine profile.

Expected use cases:

- acceptance tests for rented or procured hardware
- post-incident machine verification
- fleet qualification in CI or cluster bring-up

## Information layers

The CLI should expose more detail by moving sideways to a more specific command,
not by overloading the default output.

Recommended layering:

1. `omnismi`
   Human-first current machine summary
2. `omnismi --wide`
   More device columns and backend/runtime context
3. `omnismi doctor`
   Explanations, mismatches, missing dependencies, partial metrics
4. `omnismi bench ...`
   Empirical probing
5. `omnismi validate-spec`
   Profile-aware pass/warn/fail decision

This keeps the main entry approachable while still making deeper workflows
discoverable.

## Default overview experience

The default terminal view should feel more modern than `nvidia-smi` or
`rocm-smi`, while still being easy to scan in plain terminals.

Recommended layout:

1. Header block
   Show host, environment type, Omnismi version, and overall status.
2. Runtime block
   Show visible vendors, detected backends, and runtime visibility summary.
3. Device table
   Show one row per visible device with normalized fields.
4. Warnings block
   Show partial metrics, missing backends, permission issues, or visibility mismatches.

Presentation rules:

- prefer one compact screen over long scrolling output
- show the most decision-relevant metrics first
- keep per-device rows visually aligned
- reserve backend-level detail for the runtime or warnings blocks
- use short status words: `OK`, `PARTIAL`, `ERROR`, `EMPTY`
- avoid raw stack traces or vendor exception class names in the default view
- keep the default row compact enough to remain usable on 8, 32, and 64-device nodes
- let color help scanability, but never make it required to understand the screen

Recommended default device columns:

- `INDEX`
- `VENDOR`
- `NAME`
- `MEM`
- `UTIL`
- `TEMP`
- `POWER`
- `STATE`

Where possible:

- `MEM` should render as `used / total`
- `STATE` should summarize `OK`, `PARTIAL`, or `ERROR`
- color should be helpful but optional

### Example default view

```text
Omnismi 1.1.0-dev  host=worker-a17  env=container  status=OK
Visible accelerators: 2  vendors=nvidia  scope=runtime-visible

INDEX  VENDOR  NAME               MEM            UTIL  TEMP  POWER  STATE
0      nvidia  NVIDIA H100 PCIe   12.5 / 80.0GB  71%   58C   246W   OK
1      nvidia  NVIDIA H100 PCIe   11.9 / 80.0GB  65%   56C   239W   OK

Tips:
- Run `omnismi --wide` for more columns.
- Run `omnismi doctor` if visibility or metrics look wrong.
```

## Expected terminal previews

These previews are intentionally concrete so implementation work has a visible UX target.

### `omnismi`

This is the primary human-facing entrypoint.

```text
Omnismi v1.1.0-dev [Host: worker-a17] [IP: 192.168.1.50] [Uptime: 12d 4h]
 ─────────────────────────────────────────────────────────────────────────────
 [SYSTEM] CPU: 12% | Mem: 128.0GB/512.0GB | Driver: 550.54.15
 [VISIBLE] Devices: 2 | Vendors: nvidia(2) | Scope: container | Torch: 2
 ─────────────────────────────────────────────────────────────────────────────

  ID  NAME               TEMP   LOAD               MEMORY  POWER  STATE
┌────────────────────────────────────────────────────────────────────────────┐
│  0  NVIDIA H100 PCIe  58°C  [|||| ]  12.0GB / 80.0GB  246W   OK         │
│  1  NVIDIA H100 PCIe  57°C  [|||| ]  13.0GB / 80.0GB  245W   OK         │
└────────────────────────────────────────────────────────────────────────────┘

Tips:
- Run `omnismi --wide` for driver and runtime detail.
- Run `omnismi doctor` if visibility or metrics look wrong.
```

### `omnismi --wide`

Wide mode should add context without becoming a diagnostics dump.

```text
Omnismi v1.1.0-dev [Host: worker-a17] [IP: 192.168.1.50] [Uptime: 12d 4h]
 ─────────────────────────────────────────────────────────────────────────────
 [SYSTEM] CPU: 12% | Mem: 128.0GB/512.0GB | Driver: 550.54.15
 [VISIBLE] Devices: 2 | Vendors: nvidia(2) | Scope: container | Backends: nvml:ok
 ─────────────────────────────────────────────────────────────────────────────

  ID  NAME               TEMP   LOAD                  MEMORY  POWER  DRIVER     STATE
┌───────────────────────────────────────────────────────────────────────────────────────┐
│  0  NVIDIA H100 PCIe  58°C  [|||| ]  12.0GB / 80.0GB (15%)  246W  550.54.15  OK    │
│  1  NVIDIA H100 PCIe  57°C  [|||| ]  13.0GB / 80.0GB (16%)  245W  550.54.15  OK    │
└───────────────────────────────────────────────────────────────────────────────────────┘

Runtime:
- execution_scope=container
- torch_visible_device_count=2
- backend_status=nvml:ok
```

### `omnismi` on a no-GPU environment

No-device results should still feel intentional and useful.

```text
Omnismi v1.1.0-dev [Host: ci-runner-12] [Status: EMPTY]
 ─────────────────────────────────────────────────────────────────────────────
 [SYSTEM] CPU: -- | Mem: -- | Driver: Unavailable
 [VISIBLE] Devices: 0 | Vendors: none | Scope: container
 ─────────────────────────────────────────────────────────────────────────────

No supported accelerators are visible in the current runtime.

Hints:
- This is expected on CPU-only environments.
- Run `omnismi doctor` to inspect backend imports and runtime visibility.
```

### `omnismi doctor`

Doctor mode should explain problems in plain language before surfacing raw details.

```text
Omnismi Doctor v1.1.0-dev [Host: trainer-03] [Scope: container] [Status: WARN]
 ─────────────────────────────────────────────────────────────────────────────
 [FINDINGS]

- PyTorch reports 1 visible NVIDIA GPU, but Omnismi found 0.
- NVIDIA backend import succeeded, but device enumeration failed.
- AMD backend is not installed in this environment.

[POSSIBLE CAUSES]
- The container runtime mounted CUDA userspace but not NVML device access.
- Permissions or driver/runtime injection are incomplete.

[BACKENDS]
- nvidia / nvml: error  reason="nvmlDeviceGetCount failed"
- amd / amdsmi: missing_dependency
- google / tpumonitoring: skipped

[NEXT STEPS]
- Confirm the current pod/container has GPU device access.
- Compare `torch.cuda.device_count()` with `omnismi -o json`.
```

### `omnismi bench bandwidth`

Bench output should stay readable to humans even before users opt into structured formats.

```text
Omnismi Bench  host=worker-a17  probe=bandwidth  profile=h100-pcie-80gb

DEVICE  CASE            RESULT  BANDWIDTH   RATIO   STATE
0       copy_fp32_1gib  PASS    1.92 TB/s   0.94x   OK
1       copy_fp32_1gib  PASS    1.89 TB/s   0.93x   OK

Summary:
- 2 / 2 results passed profile thresholds.
- Run `omnismi bench bandwidth -o yaml` to save the full report.
```

## Scaling rules for large accelerator counts

The default overview must remain usable on dense nodes.

Guidelines:

- keep one compact device row per accelerator in the default view
- avoid default columns that grow with vendor-specific metadata
- use `--wide` for extra detail instead of bloating the main row
- preserve stable ordering by Omnismi global index
- favor vertical scrolling over horizontally unreadable tables on 32 and 64-device hosts
- shrink name width and low-priority columns before allowing the table to become unreadable

Future CLI extensions may add optional sections for:

- top processes by accelerator memory use
- topology or affinity summaries
- condensed vendor-group summaries ahead of the per-device table

## Rendering behavior

The table renderer should behave predictably across terminal sizes.

### Narrow terminals

- keep the header and warnings blocks
- drop low-priority columns before truncating critical ones
- prioritize `INDEX`, `NAME`, `MEM`, `UTIL`, and `STATE`
- allow `TEMP`, `POWER`, and `DRIVER` to disappear before critical columns do

### Color and symbols

- color is additive, not required for comprehension
- the ASCII words `OK`, `PARTIAL`, `WARN`, `FAIL`, and `EMPTY` should remain the core status contract
- avoid relying on Unicode icons for meaning
- support `--color auto|always|never` with `--no-color` as an alias for `never`

### Truncation rules

- truncate long device names from the right only when needed
- never truncate numeric columns mid-value
- prefer dropping columns over wrapping rows

## Structured output contract

Discovery-oriented commands should share one report family, just as
benchmark-oriented commands share `BenchReport`.

### Top-level shape

```yaml
apiVersion: omnismi/v1alpha1
kind: OverviewReport
metadata:
  generated_at: "2026-04-23T08:11:02Z"
  omnismi_version: "1.1.0-dev"
command:
  argv: ["omnismi", "-o", "yaml"]
  output: "yaml"
environment:
  platform: "linux"
  hostname: "worker-a17"
  execution_scope: "container"
  orchestrator: "kubernetes"
  torch_visible_device_count: 2
backends:
  - vendor: "nvidia"
    backend: "nvml"
    status: "ok"
    reason: null
  - vendor: "amd"
    backend: "amdsmi"
    status: "missing_dependency"
    reason: "amdsmi import failed"
inventory:
  devices:
    - index: 0
      vendor: "nvidia"
      name: "NVIDIA H100 PCIe"
      uuid: "GPU-1234"
      driver: "550.54.15"
      memory_total_bytes: 85899345920
      metrics:
        utilization_percent: 71.0
        memory_used_bytes: 13421772800
        temperature_c: 58.0
        power_w: 246.0
summary:
  device_count: 2
  healthy_device_count: 2
  partial_device_count: 0
  error_device_count: 0
  visibility_status: "MATCHED"
  warnings: []
```

### Overview report fields

- `apiVersion`: versioned schema identifier
- `kind`: `OverviewReport`
- `metadata`: generation metadata
- `command`: invocation metadata
- `environment`: execution context
- `backends`: backend availability and import/runtime reasons
- `inventory`: visible devices and normalized current metrics
- `summary`: quick rollup for terminal UX and automation

### Environment fields

`environment` should stay intentionally small and useful:

- `platform`
- `hostname`
- `execution_scope`: `host|container|unknown`
- `orchestrator`: `kubernetes|none|unknown`
- `torch_visible_device_count`

`torch_visible_device_count` is optional and only populated when Omnismi can
inspect the relevant runtime safely.

## Environment support contract

Omnismi should be explicit about where discovery and diagnostics are expected to work.

### Target execution contexts

| Context | Discovery target | Notes |
|---|---|---|
| GPU host with vendor runtime/userspace | First-class | Main development and validation path |
| GPU container on a supported host | First-class | Must respect runtime-scoped visible devices |
| Kubernetes GPU pod via device plugin/runtime injection | First-class | Must behave like the container actually sees, not like the whole host |
| CPU-only host/container | Safe no-device result | Empty inventory is valid and should not be an error |

### Discovery parity expectation

For supported GPU vendors, Omnismi discovery should aim to match the set of
visible logical devices available to the current execution environment.

In practical terms:

- if the current host or container can use a GPU through the supported vendor runtime,
  Omnismi should surface that GPU in the main discovery command
- if a container only sees a subset of host GPUs, Omnismi should only report that subset
- if PyTorch can enumerate visible GPUs in the current environment, Omnismi should
  aim to expose the same visible logical device set for the corresponding supported vendor

Any mismatch should be treated as a bug or surfaced clearly in `omnismi doctor`
with an explanation such as missing backend dependency, permission issue, or
unsupported runtime path.

### Kubernetes and device-plugin expectations

Omnismi should not assume it is running on the full host.

For Kubernetes and similar runtime-scoped environments:

- discovery should report only the devices mounted or injected into the current pod/container
- structured output should indicate that the execution scope is `container` when detectable
- host-global assumptions should never leak into the default overview

## Relationship to Bench

`omnismi` is the discovery layer.

`omnismi bench` should reuse the same `inventory` concept and device scoping
rules, but add empirical measurements and optional profile comparison. In other
words, `bench` should feel like a natural extension of `overview`, not a
separate product.

## Non-goals

- Emulating every admin-oriented field from vendor-specific SMI tools
- Exposing host-global devices from inside a container that only sees a subset
- Requiring users to read vendor logs before understanding a simple visibility problem
