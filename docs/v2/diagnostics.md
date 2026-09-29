# Agent-native diagnostics

All interpretation runs offline from a versioned packaged catalog. Current coverage:
109 active entries from the current NVIDIA Xid table, 68 PPU001 and 87 PPU0015 XIDs,
and 9 AMD RAS / PCIe AER / PPU ECC rules: **273 rules**. Vendor tables are reduced
to numeric/client facts, applicability flags and original summaries; entire manuals
are not redistributed. Rules cite source URLs/review dates; imported vendor tables
also carry source hashes.

```bash
omnismi decode --vendor nvidia --namespace xid --code 119 --model H100
omnismi decode --vendor alibaba --namespace xid-ppu0015 --code 4997
omnismi diagnose --input kernel.log
omnismi diagnose --input umc-counts.txt --format ras --block umc --pci-address 0000:41:00.0
omnismi diagnose --input normalized.json --format events
omnismi diagnose --collect passive --timeout 5
omnismi diagnose --collect hardware --timeout 30
omnismi diagnose --collect hardware --vendor alibaba --timeout 30
omnismi diagnose --self-test --vendor nvidia --device 0 --memory-mib 64 --timeout 30
```

`decode_error`, `diagnose`, `collect_hardware` and `run_probe` are public module-level
Python entry points in `omnismi.diagnostics`, `omnismi.diagnostics.hardware` and
`omnismi.probe_runtime`. They return dictionaries suitable for JSON; no LLM or web
request occurs. New CLI commands return JSON and 0/1/2/3 for PASS/WARN/FAIL/INCONCLUSIVE,
64 for bad input. Error severity is not a current hardware-health verdict.

## Normalized observations

`--format events` accepts an array, for example:

```json
[{"vendor":"alibaba","namespace":"xid-ppu0015","code":4997,"pci_address":"0000:41:00.0","timestamp":"12.5","time_basis":"boot_relative"}]
```

This boundary lets any vendor command collector supply evidence without teaching
an agent to reinterpret a manual. Each event explicitly names vendor/namespace.
PPU generations are separate namespaces because code meanings/clients differ.
Unknown generations/codes remain INCONCLUSIVE. Never reuse NVIDIA Xid meanings
for PPU or Cambricon events. RAS counters use their dedicated input format with
block and PCI identity rather than pretending to be Xid codes.

Kernel parsing recognizes NVRM Xid (including `PCI:` addresses), preceding driver
UUID lines and PCIe AER severities. Identity joins preserve omitted PCI function
numbers. Unknown dmesg prose is retained as unmatched evidence. Repeated findings
share their explanation but preserve evidence IDs and UUID identity.

## Collection and self-test

`--collect passive` only reads dmesg. `--collect hardware` runs an isolated worker
that combines bounded dmesg, vendor management inventory/metrics, AMD RAS sysfs
counter files and documented PPU ECC counters. UUIDs bind PPU telemetry to inventory;
CNDEV per-field return codes explain missing metrics. Nonzero historical counters
carry explicit volatile/aggregate or snapshot-not-delta semantics. A timeout,
missing SDK or permission failure is incomplete evidence, never a healthy result.

`--self-test` explicitly runs copy and vector-add correctness checks with four
representable data patterns, then a small matrix multiplication. It runs only on
the selected compute-runtime index, in a subprocess killed on deadline. It neither
resets devices nor modifies other processes. The tensor budget is 1..4096 MiB;
it excludes runtime context, allocator and library workspace overhead. Tests cover
allocated buffers/operations only and cannot certify the entire card or prove a
specific physical unit is faulty. Runtime exceptions are INCONCLUSIVE; observed
wrong results are FAIL with unconfirmed hardware causality.

NVIDIA/AMD torch, modern torch_mlu and native SAIL HGGC are implemented runtime
paths. PPU self-test uses the separately SDK-compiled probe from
[the PPU guide](alibaba-ppu.md); its device indexes belong to HGGC. Real target-host
validation remains required for each vendor.

## Interpretation boundaries

NVIDIA rules retain current catalog model flags and reference recovery buckets.
An explicitly excluded A100/H100/B100/GB200 model is INCONCLUSIVE. Unrecognized
model names and driver strings are retained as context, not certified. Recovery
buckets are references only; no reset/reboot/action is executed. Informational
catalog events such as SMBPBI test messages do not become fault verdicts.

Top-level Xid decoding does not implement revision-dependent IntrInfo/subcode
recovery logic. Current-health, exact event age, causality, transient-versus-permanent
failure and complete board coverage require additional evidence. Unknown codes
always remain explicit rather than receiving a guessed closest match.

Input bounds: 1 MiB, 500 nonblank/normalized events, 4096 characters per log line.
Truncated identifiers are never interpreted as a different code. Raw sanitized log
lines are opt-in with `--include-raw`; active and hardware modes report structured
observations. Vendor command output and SDK hangs are bounded by the worker.
