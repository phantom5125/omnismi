# Cambricon CNDEV adapter

The optional Cambricon backend is implemented on `codex/v2-runtime-completion`.
No model has been hardware-validated. The adapter uses a read-only native process,
compiled on the target Linux machine against its installed CNDEV headers/library.
Python never guesses the layouts of proprietary SDK structs or loads their ABI.

## Build and query

```bash
mkdir -p bin
omnismi cndev-build --include-dir /path/to/sdk/include --library-dir /path/to/sdk/lib64 --output "$PWD/bin/omnismi-cndev-probe"
export OMNISMI_CNDEV_PROBE="$PWD/bin/omnismi-cndev-probe"
omnismi --vendor cambricon --output json
omnismi diagnose --collect hardware --vendor cambricon
```

Alternatively place the compiled `omnismi-cndev-probe` on PATH. Imports never
compile code or install a driver. Building requires `cc`, matching `cndev.h` and
`libcndev`, and the CNDEV_VERSION_6 APIs used by the official exporter. The build
refuses an existing output and returns header/source hashes for evidence records.
A missing/incompatible header, symbol or library fails the compile/link step.

The collector initializes/releases CNDEV per process and emits a versioned JSON
snapshot. Each execution has a 5-second / 1-MiB budget and process-group cleanup;
a native crash/hang does not crash the Python caller. Snapshots are cached for
0.5 seconds on demand. UUID handles reject device replacement across refreshes.
Missing metrics remain null, with native return codes in passive hardware reports.

Coverage: model, UUID, driver, physical memory used/total (MiB converted to bytes),
utilization (%), board temperature (C), power (W), core/DDR clock (MHz).
Physical management enumeration is not proof of process-runtime access or MIM/SMLU
visibility. Unsupported API calls remain unavailable. There is no selected model,
SDK download, device reset or configuration change.

## Evidence for the implementation

The [official exporter at the pinned revision](https://github.com/Cambricon/mlu-exporter/tree/648a19c7d781ada2ea693e46edc562aa57f79be4)
provides API call signatures/fields in `pkg/cndev/cndev.go`, memory conversion in
`pkg/collector/cndev.go`, and metric units in `examples/metrics.yaml`. Its README
requires header version 6.5.24 from a driver package. That header is not redistributed
here; compilation uses the user's matching header and vendor library. See
`cambricon-api-map.json` for the interface inventory.

Modern [torch_mlu](https://github.com/Cambricon/torch_mlu) can provide the explicit
self-test/performance runtime via `--vendor cambricon`. It must be installed using
the vendor's matching PyTorch/Neuware distribution. Omnismi does not install or
silently replace PyTorch. Missing runtime APIs yield INCONCLUSIVE.

Tests cover SDK absence, UUID replacement, invalid metrics, null versus zero,
MiB conversion, and compiling/running the C boundary with a synthetic SDK. Real
SDK compilation and hardware parity remain required before marking any card
verified. `🧪 Awaiting User Validation` does NOT mean unsupported.
