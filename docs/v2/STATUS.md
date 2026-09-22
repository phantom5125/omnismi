# 2.0 development delivery status

Updated 2026-09-22. `codex/v2-preview` combines the initial implementations so
they can be installed and exercised together. Feature PRs remain independent
drafts against `codex/v2-integration`. This is not a 2.0 release or a claim of
hardware validation. The package version remains 1.0.0 during development.

## Delivered increments

| Track | Branch / draft PR | Available now | Remaining work |
|---|---|---|---|
| Diagnosis | `codex/v2-diagnostics` / [#6](https://github.com/phantom5125/omnismi/pull/6) | Packaged offline catalog with 15 source-backed rules; NVIDIA Xid and PCIe AER log normalization; explicit AMD RAS counter input; bounded passive dmesg collection; structured evidence and affected-unit hypotheses | Wider version-specific catalogs, event correlation, active self-tests, PPU/Cambricon rules and hardware evidence |
| Performance | `codex/v2-perf-doctor` / [#7](https://github.com/phantom5125/omnismi/pull/7) | BenchReport import; matching run conditions; separate measured/expected-sustained and measured/theoretical-peak percentages; explicit provenance and threshold policy | Curated real-device baselines, repeated probe execution, additional workload types and diagnostic correlation |
| Topology | `codex/v2-topology-affinity` / [#8](https://github.com/phantom5125/omnismi/pull/8) | Linux PCI/NUMA/NIC/RDMA graph; permitted-locality affinity suggestions; saved NVIDIA topology matrix import | Live vendor interconnect collectors, stable cross-tool identity joins, MIG/partition modeling and hardware validation |
| Alibaba PPU | `codex/v2-alibaba-ppu` / [#9](https://github.com/phantom5125/omnismi/pull/9) | Experimental documented SAIL PPU-SMI CSV adapter for identity, driver and memory snapshots | Other telemetry, runtime visibility, native HGML binding, topology/error capabilities and hardware parity |
| Cambricon | `codex/v2-cambricon` / [#10](https://github.com/phantom5125/omnismi/pull/10) | Official CNDEV usage mapped to a pinned source revision; ABI requirements documented | Adapter implementation requires matching CNDEV headers/manuals or an SDK environment; no target card has been selected |

Preview inputs: diagnostics `575a9dd`, performance `4e5465f`, topology `c9af6f9`,
PPU `1bfb5db`, and Cambricon research `684210a`. The preview snapshot resolves
shared CLI dispatch/source-index conflicts and includes unified help and delivery
documentation. It does not merge or close the feature PRs.

## Try the preview

Install this branch from its checkout in an isolated environment:

```bash
python -m pip install .
omnismi decode --vendor nvidia --namespace xid --code 48
omnismi diagnose --input kernel.log
omnismi perf-doctor --input examples/performance/synthetic-measurement.json --baseline examples/performance/synthetic-baseline.json
omnismi topology
omnismi --vendor alibaba --output json
```

Diagnosis/performance/topology commands always emit JSON. Their exit codes are
0 PASS, 1 WARN, 2 FAIL where applicable, 3 INCONCLUSIVE and 64 invalid input.
The synthetic performance example intentionally returns WARN (exit 1), with 80%
of expected sustained and 40% of theoretical peak. It is not a hardware baseline.
Xid 48 reports a severe historical event, not confirmation of current bad hardware.

Live topology and passive dmesg collection require Linux. PPU collection requires
the vendor-installed `ppu-smi` on PATH. There is no SDK installation or active
self-test during these calls. Ordinary offline diagnosis has no network dependency.

## Validation and release gates

- Combined regression suite: 134 passed on the local Python 3.12 environment.
- Individual feature suites: diagnostics 73, performance 76, topology 54, PPU 54.
- Wheel and sdist builds include the offline JSON catalog.
- A clean Python 3.12 wheel install without vendor extras passes command help,
  catalog decoding, stdin diagnosis, the synthetic 80%/40% comparison, non-Linux
  topology handling and the missing-SDK PPU CLI path.
- New standalone modules/tests pass Ruff and Black. Existing whole-repository
  formatting/lint debt predates this work and is not represented as passing.
- No new hardware adapter or topology/diagnostic capability has been tested on a
  physical accelerator. Existing compatibility labels have not been upgraded.

The existing CLI foundation and overlapping [PR #5](https://github.com/phantom5125/omnismi/pull/5)
still require one agreed command/schema baseline before a main-branch release.
Review the independent feature PRs, collect SDK/hardware evidence, then complete
the remaining feature gates above before calling this 2.0 complete.

For Cambricon, the next missing input is the version-matched `cndev.h` and API/unit
documentation (the official exporter currently requires header version 6.5.24),
or an environment with that SDK installed. A specific card is only needed for
the subsequent hardware validation, not to select the shared interface.
