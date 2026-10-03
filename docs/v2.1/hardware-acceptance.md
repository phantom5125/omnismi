# Real-device acceptance (2.1 preview)

Run a repeatable test on one device, retain the evidence, then expand to more
devices and runtimes. Start with **one fixed Pod or VM**, not a large batch.
This workflow is implemented on `codex/v2.1-hardware-selftest`; it is not in the
published 2.0.0 package. All four target presets still await real-device acceptance.

`omnismi self-test campaign` runs existing CPU-reference checks in stages. It
records the environment and device identity, stops on a mismatch or incomplete
evidence, and creates a portable archive. It does not provision instances,
install compute runtimes, change power limits, upload files or stop cloud billing.

## What acceptance establishes

| Question | Evidence required | What it does not establish |
|---|---|---|
| Does this adapter work on this model? | All selected cases run and meet their comparisons on the identified device. | Every device of that model is healthy. |
| Are results repeatable? | Repeat the same seed in a fresh worker, then another seed and physical device. | Every possible shape, input or runtime is covered. |
| Were checks run under a stated power condition? | An explicit watt target and sufficient fresh, UUID-attributed load samples. | Continuous maximum power or every electrical transient was exercised. |
| Can the suite detect a real fault? | Retained failures on known faulty hardware, with a normal control and independent investigation. | A detection rate from a few normal rental cards. |
| Was every physical unit tested? | Native dispatch/unit observations and an applicable coverage model. | Current operator tests cannot provide this; coverage remains **UNKNOWN**. |

The first three are separate acceptance dimensions. A normal-card `PASS` does
not establish SDC sensitivity. Numerical mismatches require investigation of
hardware, drivers, frameworks, compilers and the reference itself.

## 1. Choose a device and freeze the environment

Recommended order for this project:

| Target | Initial environment | Notes |
|---|---|---|
| `rtx-5090` | One RunPod GPU Pod with compatible CUDA PyTorch | Run the pilot before committing to longer sessions. |
| `b300` | One B300 Pod with compatible CUDA PyTorch | One runtime-visible GPU; this does not validate a DGX or NVLink fabric. |
| `mi355x` | An actual MI355X host with vendor-supported ROCm PyTorch | RunPod's reviewed list names MI300X, not MI355X. MI300X cannot satisfy this target. |
| `tpu-v6e` | A v6e TPU VM with a working JAX TPU runtime | Tests one local runtime device, not the entire TPU slice or ICI network. |

RunPod lists RTX 5090 and B300, but a listing does not guarantee capacity in a
region. Check availability and the quoted price at booking time. Using fixed
Pods for the first campaign is our recommendation: it makes the environment,
identity and evidence easier to retain than request-scheduled workers.
[RunPod GPU types](https://docs.runpod.io/references/gpu-types),
[Pods overview](https://docs.runpod.io/pods/overview).

On RunPod, select a single GPU and a maintained, compatible PyTorch image.
Record the Pod ID, image digest, host driver, runtime versions, quoted hourly
price and a spending limit in your operator notes. Avoid unrelated workloads
during acceptance. Container access does not guarantee host kernel logs or
host driver control. For TPU, use a configured v6e TPU VM and verify the
vendor-supported JAX installation first; do not substitute a CPU JAX runtime.
[TPU v6e](https://docs.cloud.google.com/tpu/docs/v6e),
[JAX on TPU VMs](https://docs.cloud.google.com/tpu/docs/run-calculation-jax).

Install the preview **inside that working runtime environment**. Use the same
reviewed Git commit across all comparison runs. Set `OMNISMI_REV` to its full
40-character hash (from the PR), not a moving branch name:

```bash
: "${OMNISMI_REV:?Set OMNISMI_REV to the reviewed full Git commit hash}"
git clone --branch codex/v2.1-hardware-selftest https://github.com/phantom5125/omnismi.git
cd omnismi
git checkout --detach "$OMNISMI_REV"
git rev-parse HEAD
python -m pip install -e '.[nvidia,selftest]'
omnismi self-test campaign --plan --target rtx-5090 --suite acceptance
```

This install example includes NVIDIA management telemetry. On AMD or TPU, use
`'.[selftest]'` and the management libraries supplied by the compatible vendor
environment (AMD SMI or LibTPU). Preserve the working runtime's version pins.
The `selftest` extra supplies NumPy, not CUDA/ROCm PyTorch or JAX/TPU. A fresh
virtual environment must have access to the chosen compute runtime. Plans need
no accelerator or compute framework. Pin the image and commit in your operator
notes; `--image-ref` and `--instance-label` are operator-supplied provenance,
not independently verified device identities.

## 2. Run a pilot

Use a fresh output directory for every invocation. This example assumes RunPod
and a runtime-visible RTX 5090 at index 0:

```bash
omnismi self-test campaign --run --target rtx-5090 --suite pilot \
  --device 0 --provider runpod \
  --output-dir /workspace/omnismi-evidence/5090-pilot-01
```

The pilot runs only `01-smoke` (at most 120 seconds in its worker by default).
Read `campaign.json` and the stage's `report.json`. Continue only after `PASS`.
An unavailable runtime, wrong model, unsupported operation, skipped comparison,
timeout or missing evidence yields `INCONCLUSIVE`; inspect the reason before
spending on more devices. There is no silent CPU fallback.

`--device` is the **compute runtime index**, which can differ from management
tool indices. One invocation selects one visible device or partition. Changing
visibility masks can change what index 0 means.

## 3. Run the full campaign

```bash
omnismi self-test campaign --run --target rtx-5090 --suite acceptance \
  --device 0 --seed 42 --memory-mib 256 \
  --stage-timeout 900 --duration 300 --provider runpod \
  --output-dir /workspace/omnismi-evidence/5090-acceptance-01
```

For other environments, change `--target` and `--provider` (`local`, `runpod`,
`gcp` or `other`). Set an appropriate existing output parent on non-RunPod hosts.
Optional `--instance-label` and `--image-ref` accept your recorded identifiers.

| Stage | Purpose |
|---|---|
| `01-smoke` | Confirm runtime identity and basic comparisons. |
| `02-extended` | Exercise the target's extended operator, shape and dtype matrix. |
| `03-repeat` | Repeat the same configuration and seed in a fresh worker. |
| `04-new-seed` | Run the extended matrix with seed + 1 (wrapping at 2³²). |
| `05-load` | Interleave matrix load with independent comparisons, then check cases again. |
| `06-post-smoke` | Check basic behavior again in another fresh worker. |

Each stage uses one isolated, deadline-bounded worker. The default sum of worker
timeouts is **64 minutes**; this is an upper bound for the selected worker
deadlines, not an expected runtime or cloud spending cap. Setup, inventory,
archiving and idle rental time are additional. The nominal load duration is
5 minutes; increasing it also requires a longer `--stage-timeout`.

The suite checks `topk` independently; passing `sort` does not cancel a `topk`
failure. The lost parameters from the earlier Blackwell incident are not known,
so this matrix does not claim to reproduce that exact incident. Same-seed
repetition repeats generated inputs; it does not force identical GPU scheduling.

Load includes CPU comparisons and transfers. It is not uninterrupted maximum
power stress. In-worker post-load checks reduce the gap before rechecking;
`06-post-smoke` includes fresh-worker startup and is not a guaranteed hot-state
measurement. `--memory-mib` bounds case working-set estimates, not total process
memory, framework allocations or full VRAM coverage.

### Optional power-conditioned run

After the basic campaign works, determine an appropriate watt threshold from
the actual device, permitted power policy and observed normal load. Do not copy
a board's advertised TDP and assume the workload will sustain it. Run a **new**
acceptance campaign with `--power-target-w WATTS` and a fresh output directory.

The power gate requires a matching runtime UUID, at least three fresh load
samples, and at least 80% at or above the requested threshold. If readings are
unavailable, attribution fails or the target is not sustained, the result is
`INCONCLUSIVE`. With no threshold, `power_validation` is `NOT_REQUESTED` even
when all comparisons pass. This command does not adjust clocks or power limits.
TPU power attribution is currently unavailable; do not claim high-power TPU
validation from a successful operator run.

## 4. Keep and inspect the evidence

Normal completion, mismatches and handled interruptions produce:

```text
5090-acceptance-01/
  campaign.json             # Overall verdict, stages, identity and limits
  environment.json          # Python/package versions, source revision, visibility
  inventory-before.json     # Management inventory; not an ordinal device match
  inventory-after.json
  inventory-*.stderr.txt
  01-smoke/report.json
  02-extended/report.json    # Later stages only exist if reached
  .../evidence/*.npz        # Mismatch inputs/results when the worker saved them
  checksums.json            # SHA-256 for retained files, excluding itself
5090-acceptance-01.tar.gz
```

The manifest is checkpointed between stages. The first non-PASS stops further
stages; no automatic retry hides the original outcome. Run again in a new
directory and retain both attempts. There is no resume operation. A forced
kill or machine loss may leave only partial evidence; a RUNNING stage is never
PASS. Storage failure can prevent a complete archive. Retain JSON and any
available NPZ files even when the command exits nonzero.

The archive contains local paths, device identifiers and environment details.
Review these before publishing a public issue. Only an allowlist of device
visibility environment variables is recorded; environment variables are not
dumped wholesale. Checksums detect accidental changes, not authenticity.

| CLI exit | Manifest status | Action |
|---|---|---|
| 0 | PASS | All stages in **this selected suite** passed; preserve the scope. |
| 2 | FAIL | Numerical mismatch observed; retain evidence and investigate. |
| 3 | INCONCLUSIVE | Evidence incomplete or a gate unmet; inspect reasons. |
| 64 | INCONCLUSIVE error | Invalid configuration or output setup; correct it. |

For `--plan`, exit 0 means the plan was produced, not that hardware passed.
`physical_unit_coverage=UNKNOWN`, `current_hardware_health=INCONCLUSIVE`,
`hardware_fault_confirmed=false` and `known_fault_detection=NOT_ASSESSED`
remain unchanged even for a passing campaign. A pilot PASS does not imply a
full acceptance PASS. The `hardware_acceptance` schema is version 1.

Download reports and inspect an individual stage on your own computer:

```bash
omnismi dashboard --report ./5090-acceptance-01/02-extended/report.json --open
```

The dashboard accepts stage `hardware_selftest` reports, not `campaign.json`.
NPZ evidence preserves recorded inputs for investigation; an automatic exact
NPZ replay command is not yet provided. This campaign does not collect XID/RAS
logs. Collect accessible vendor/host logs separately with timestamps and mark
unavailable logs as not collected. No reported XID does not invalidate a mismatch.

### RunPod storage and shutdown

The default `/workspace` volume survives Pod stop/restart but is deleted when
the Pod is terminated. A **network volume** is independent of the Pod and must
be attached at creation. Container-disk files can be lost on stop/restart.
Choose storage deliberately and copy the evidence off the instance before
termination. [RunPod storage types](https://docs.runpod.io/pods/storage/types),
[network volumes](https://docs.runpod.io/storage/network-volumes).

Basic proxy SSH does not support SCP/SFTP. With full SSH and a public IP, use
the actual host and port from the **Connect** panel:

```bash
# Run on your computer; replace PORT and HOST with the full SSH connection values.
scp -P PORT root@HOST:/workspace/omnismi-evidence/5090-acceptance-01.tar.gz .
```

Compare the archive's SHA-256 before and after transfer (`sha256sum` on Linux,
`shasum -a 256` on macOS), then extract and retain the directory and checksum
manifest. Inspect the recorded verdict, not merely the existence of a tar file.
After verifying the copy, manually stop/terminate the rental as appropriate and
review retained-storage charges. Finishing Omnismi does not stop billing.
[RunPod SSH options](https://docs.runpod.io/pods/configuration/use-ssh).

## 5. Expand the matrix, then test known faults

For a small project's initial compatibility claim, aim for **two independent
physical devices per target** and **two supported runtime builds** where access
permits. This is an engineering starting point, not a statistical reliability
guarantee. Keep a row per campaign:

| Field | Record |
|---|---|
| Model and physical identity | Exact reported name, UUID, partition/visibility scope |
| Allocation | Provider and instance label; host identity if available |
| Software | Omnismi commit, image digest, driver/framework/runtime versions |
| Test | Suite, seeds, budgets, power target, timestamp |
| Result | Verdict, case failures, power outcome, incomplete reasons |
| Evidence | Archive location, SHA-256, operator notes and issue link |

Different Pod IDs can refer to the same GPU. Deduplicate by physical UUID and
respect partition boundaries. Without a hardware UUID (for example the current
TPU adapter), the report says `identity_continuity=RUNTIME_ONLY`: obtain provider
evidence before counting distinct physical chips. A stopped/restarted allocation
must be treated as a fresh device until identity is rechecked.

Only after the first environment works should a scheduler fan out **one campaign
per explicitly selected device**. Retain nonzero-exit artifacts, impose a global
concurrency/spending limit, avoid competing workloads on the same device, and
keep teardown outside the test process. Do not schedule only passing retries.
No RunPod API integration or cloud batch scheduler is shipped by this command.

For detection validation, use known faulty hardware when available, with a normal
control under the same configuration. Preserve the first failure, repeat on the
same physical device, compare another physical device with the same runtime,
then compare a second supported runtime. Escalate consistent device-specific
evidence for vendor investigation; a mismatch alone does not localize a chip unit.

Software fault injection in the repository tests verifies the reporting/oracle
path only. Label it **synthetic**; never count it as real-card SDC detection.
Until known-fault evidence exists, publish compatibility results with **real SDC
detection not assessed** and physical coverage **unknown**. Do not mark a target
validated merely because cloud creation or software CI succeeded.

Provider documentation reviewed **2026-10-03**. Availability, pricing and runtime
compatibility must be checked again when booking.
