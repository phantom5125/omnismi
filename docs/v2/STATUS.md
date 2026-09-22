# 2.0 implementation and validation status

Updated 2026-09-22. The second implementation is on `codex/v2-runtime-completion`,
based on the combined `codex/v2-preview`. It closes the initial offline-only and
research-only paths with explicit workloads, live collectors, a CNDEV adapter and
native SDK-compiled SAIL probes.
The package version is still 1.0.0 on development branches; nothing was published
as a 2.0 release. Hardware certification remains a separate evidence requirement.

| Capability | Implemented | Operating boundary |
|---|---|---|
| Offline interpretation | 273 source-backed rules: 109 active NVIDIA Xids, 68 PPU001 and 87 PPU0015 XIDs, 9 RAS/AER/ECC rules; explicit normalized event JSON; source hashes/model flags | Top-level codes and documented counter semantics; unknown versions/subcodes remain inconclusive |
| Passive diagnosis | One bounded subprocess combines dmesg, vendor inventory/metrics, AMD RAS sysfs and PPU ECC counters | No reset, error injection or automatic remediation; snapshots do not establish current health |
| Active self-test | Allocated-buffer copy and vector-add patterns plus matrix multiplication with correctness checks | Explicit execution only; NVIDIA/AMD torch, modern torch_mlu and native SAIL HGGC paths; partial memory coverage |
| Performance | Repeated synchronized bandwidth and dense FP32 compute probes; retained samples/variance; baseline creation from distinct runs; exact-condition comparison | No fabricated vendor baseline or default threshold; external context must describe actual conditions |
| Topology | Linux PCI/NUMA/NIC/RDMA; live NVIDIA NVLink and PPU ICN matrices; identity queries before/after; NVIDIA MIG parent graph | Management view; incomplete/changed identity joins are reported; matrix links do not prove P2P/RDMA access |
| Affinity | Local CPUs and memory nodes intersected with effective process masks | Suggestions only; no process binding changes |
| Alibaba PPU | Full normalized management metrics, ECC and generation-specific codes; HGGC self-test, bandwidth and tiled FP32 compute; explicit SDK compiler command | SAIL v2.1.1 documented APIs/formats; CPU protocol/control tests pass; real HGGC compilation and PPU execution still require target verification |
| Cambricon MLU | SDK-compiled CNDEV collector, optional registered backend, inventory and all normalized metric fields, per-field return codes | Compile against matching installed CNDEV 6 headers/library; physical management view; no tested card model claimed |

## End-to-end commands

```bash
# Installed from this checkout, with no vendor package required for offline use.
python -m pip install .
omnismi decode --vendor nvidia --namespace xid --code 119
omnismi decode --vendor alibaba --namespace xid-ppu0015 --code 4997
omnismi diagnose --input events.json --format events
omnismi diagnose --collect hardware --timeout 30

# Explicit workloads; device indexes here belong to the compute runtime.
omnismi diagnose --self-test --vendor nvidia --device 0 --memory-mib 64 --timeout 30
omnismi perf-doctor --run bandwidth --vendor nvidia --context conditions.json --save-measurement run1.json
omnismi perf-doctor --run bandwidth --vendor nvidia --context conditions.json --save-measurement run2.json
omnismi perf-doctor --build-baseline lab-copy --measurement run1.json --measurement run2.json --policy policy.json > baseline.json
omnismi perf-doctor --input run1.json --baseline baseline.json
omnismi perf-doctor --run compute --vendor nvidia --context conditions.json --baseline compute-baseline.json
omnismi bench matmul --vendor nvidia --device 0 --memory-mib 64
omnismi bench suite --vendor nvidia --device 0 --memory-mib 64 --timeout 90

# Read-only topology and constrained affinity.
omnismi topology --collect-vendor nvidia
omnismi topology --collect-vendor alibaba
omnismi topology --recommend-affinity --device pci:0000:41:00.0

# Optional CNDEV collector, compiled on a Linux SDK host.
mkdir -p bin
omnismi cndev-build --include-dir /path/to/sdk/include --library-dir /path/to/sdk/lib64 --output "$PWD/bin/omnismi-cndev-probe"
export OMNISMI_CNDEV_PROBE="$PWD/bin/omnismi-cndev-probe"
omnismi --vendor cambricon --output json
omnismi diagnose --collect hardware --vendor cambricon

# Optional native SAIL workloads, compiled on a Linux SAIL SDK host.
omnismi sail-build --output "$PWD/bin/omnismi-sail-probe"
export OMNISMI_SAIL_PROBE="$PWD/bin/omnismi-sail-probe"
omnismi diagnose --self-test --vendor alibaba --device 0 --memory-mib 64
omnismi bench suite --vendor alibaba --device 0 --memory-mib 64 --timeout 90
```

New agent commands return JSON and exits 0 PASS, 1 WARN, 2 FAIL, 3 INCONCLUSIVE,
64 invalid input. A successful performance probe without a comparable baseline
returns INCONCLUSIVE with its measurement; `--save-measurement` still saves it.
For shell automation, preserve that output rather than discarding every nonzero
exit. Baseline construction writes baseline JSON and returns 0 on success.
A self-test PASS applies only to executed checks, never to whole-device health.

See the individual guides for conditions/policy schemas, units and fixtures.
Use a new run to evaluate a baseline; the self-comparison above demonstrates the
interface only and does not independently validate the baseline.

## Validation and remaining external evidence

Local regression, offline packaging and clean-install checks are recorded in the
change description: **198 tests pass locally**, with successful wheel/sdist builds
and clean Python 3.12 installation checks. New code has no runtime network
dependency. Tests include a
C collector compiled and linked against a deliberately synthetic CNDEV SDK,
and the SAIL worker's host-control code compiled with CPU stand-ins for the
runtime and kernels. These tests check protocols, resource limits and failure
handling; they do not certify real vendor compilation, ABI or hardware.

Still required for a hardware-validated 2.0 release:

1. Linux accelerator hosts with matching SDK/driver installations for vendor
   parity, container/runtime visibility, actual live topology and workload checks.
2. Real repeated performance runs under recorded power/clock/partition conditions
   before any built-in sustained baseline can be published.
3. Real CNDEV and HGGC builds with matching SDK headers/libraries/compiler, followed
   by card tests. Public API references and local synthetic-runtime validation
   are recorded, but do not replace these installed-SDK checks.
4. One reviewed CLI baseline reconciling existing PR #5 and the CLI foundation;
   version/release decisions and main-branch merging are still pending.

First-increment independent draft PRs remain [#6](https://github.com/phantom5125/omnismi/pull/6),
[#7](https://github.com/phantom5125/omnismi/pull/7),
[#8](https://github.com/phantom5125/omnismi/pull/8),
[#9](https://github.com/phantom5125/omnismi/pull/9), and
[#10](https://github.com/phantom5125/omnismi/pull/10). The current branch builds on
their integrated snapshot rather than changing those review bases underneath them.
