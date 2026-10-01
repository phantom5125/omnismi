# Hardware test dashboard (2.1 preview)

[中文指南](dashboard.zh-CN.md)

See the result, inspect unexpected values, and prepare a retest. The dashboard
uses the same JSON reports as agents. It is English-first, uses the existing
Omnismi logo, and requires neither Python code nor Node.js to use.

This feature is on `codex/v2.1-hardware-selftest`; it is not in the published 2.0.0 release.

## Quickstart

Use Python 3.9+ in a virtual environment:

```bash
git clone --branch codex/v2.1-hardware-selftest https://github.com/phantom5125/omnismi.git
cd omnismi
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[selftest]'
omnismi dashboard --open
```

The default address is `http://127.0.0.1:8765`. Use `--port 8766` if that port is
busy, or `--port 0` to choose an available port. Viewing reports needs no GPU or
compute framework. **Explore a demo** opens clearly labelled synthetic results;
it does not run a test or represent a real card.

1. Open **Run a test**. Select a model and start with **Quick**. Copy the plan command to check its scope.
2. Run the test command on the target machine with a compatible vendor runtime installed.
3. Import `selftest.json`. Keep JSON even after exit code 2 (mismatch) or 3 (inconclusive), along with any NPZ files in `sdc-evidence`.

For example, on an RTX 5090 machine with a compatible CUDA PyTorch installation:

```bash
omnismi self-test --plan --target rtx-5090 --profile smoke
omnismi self-test --run --target rtx-5090 --device 0 --profile smoke \
  --timeout 120 --artifact-dir ./sdc-evidence > selftest.json
omnismi dashboard --report selftest.json --open
```

`--device` is the index visible to the compute runtime. One run tests one visible
device or partition. If its model does not match `--target`, no operators run and
the result is `INCONCLUSIVE`. Other models can use the generic `--vendor` plans.
See the [self-test contract](hardware-selftest.md) for budgets and detailed limits.

## Read the results

| Result | Meaning | Next step |
|---|---|---|
| Selected checks passed | The selected cases and acceptance criteria passed. | Save the report; try more cases or repetitions. |
| Numerical mismatch found | Values, shapes or indices violate the reference or operator rules. | Keep JSON and NPZ; repeat on the same device, then compare another device or runtime. |
| More evidence needed | Checks or criteria are incomplete. | Inspect the reason: runtime, unsupported operation, time limit or missing observations. |
| Test plan · Not run yet | No computation has run. | Run the generated command on the target machine. |

- Counts refer to **test cases**, not physical hardware units. The default table groups cases by operator; filters show individual cases.
- A passing `sort` does not cancel a failing `topk`. Select a row to inspect its cases and technical details.
- Retests preserve configuration and seed. Output paths are fixed; imported paths are never inserted into shell commands. Keep NPZ files for exact input replay.
- Power charts appear only for recorded samples. Missing samples are not zero watts. A load test without an observed, met power target does not establish high-power validation.
- “XID/RAS not collected” does not mean no errors occurred. Physical coverage remains **Unknown**.
- A mismatch is evidence to investigate. Hardware, drivers, frameworks, compilers or reference code may be responsible; the report does not automatically diagnose hardware SDC.

## Hardware maps

Open **Hardware** and choose a model. Click a module to see its function, related
operators, test limitations and a link to the vendor source. The diagrams are
original, simplified explanations of selected architectural blocks. They are not
die floorplans, discovered inventories, traffic measurements or coverage heatmaps.

| Model | Blocks shown | Official architecture sources |
|---|---|---|
| RTX 5090 | CUDA and Tensor Cores, nearby storage, L2, GDDR7, PCIe, RT/media engines | [NVIDIA RTX Blackwell whitepaper](https://images.nvidia.com/aem-dam/Solutions/geforce/blackwell/nvidia-rtx-blackwell-gpu-architecture.pdf), especially SM Architecture and the RTX 5090 specifications |
| B300 | Blackwell-family compute/storage, HBM3E, PCIe and NVLink | [Blackwell tuning guide](https://docs.nvidia.com/cuda/blackwell-tuning-guide/index.html), [Blackwell Ultra architecture](https://developer.nvidia.com/blog/?p=104887), [DGX B300 guide](https://docs.nvidia.com/dgx/dgxb300-user-guide/introduction-to-dgxb300.html) |
| MI355X | Vector ALUs and Matrix Cores within CUs/XCDs, LDS/L1, L2/Infinity Cache, HBM3E, PCIe and Infinity Fabric | [AMD CDNA 4 whitepaper](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/white-papers/amd-cdna-4-architecture-whitepaper.pdf), Figures 3 and 5 and communication sections |
| TPU v6e | Vector/scalar units and MXUs within a TensorCore, HBM, ICI and SparseCore | [Google TPU v6e system architecture](https://docs.cloud.google.com/tpu/docs/v6e) |

Sources reviewed **2026-10-02**. Diagram labels describe static architecture;
**operator-to-module associations are Omnismi interpretations**, not measured
dispatch or vendor diagnostic claims. A successful `matmul` does not prove a
Tensor Core, Matrix Core or MXU was used. Cache, register and interconnect tests
are not isolated by the current suite. Memory checks do not sweep all addresses.
Repeated units, internal links and some specialized engines are omitted.

Related report results appear only when its explicit target, vendor and reported
identity match the selected model. Plans, ambiguous identities and other models
have no attached execution evidence. Synthetic reports stay labelled. Neither a
passing nor a failing operator changes a module's physical coverage from Unknown.

The machine-readable descriptions live in
[`hardware.json`](https://github.com/phantom5125/omnismi/blob/codex/v2.1-hardware-selftest/src/omnismi/selftest/hardware.json)
and are packaged with Omnismi. They include module purposes, operator associations,
limitations, source references and a review date. The dashboard reads this catalog;
it makes no network request to retrieve whitepapers while viewing a report.

## Initial hardware targets

| Target | Runtime | Extended data types | Status |
|---|---|---|---|
| `rtx-5090` | CUDA / PyTorch | FP32, FP16, BF16, INT32 | Adapter implemented; real-device validation pending |
| `b300` | CUDA / PyTorch | FP32, FP16, BF16, INT32 | Adapter implemented; real-device validation pending |
| `mi355x` | ROCm / PyTorch | FP32, FP16, BF16, INT32 | Adapter implemented; real-device validation pending |
| `tpu-v6e` | JAX / TPU | FP32, BF16, INT32; BF16 load | Adapter implemented; real-device validation pending |

Selection reflects project priorities and runtime diversity, not measured defect
rates or a popularity ranking. Numeric-format cases do not cover every instruction
or unit supporting that format. No whole-DGX, NVLink fabric or TPU-slice coverage
is claimed. Cambricon still needs a target model; the PPU SDC executor is pending.

For each target: Quick → Extended → repeated Extended → bounded Load. First check
normal hardware for execution and false positives, then compare known failures or
controlled fault injection. Retain identity, visibility, runtime versions, seeds,
JSON/NPZ and power attribution before marking real-device validation complete.

## Local data and compatibility

The viewer binds only to `127.0.0.1`. It serves bundled assets and, optionally, the
single report selected with `--report`. It cannot browse your disk or start a
workload over HTTP. Reports are validated in the browser (up to 8 MiB;
`schema_version=1`, `report_type=hardware_selftest`). Invalid imports leave the
previous report intact. Exports preserve the synthetic marker when present.

Reports stay in the current page session, with no persistent browser storage,
uploads, remote fonts or telemetry. External sources open only when clicked.
Reloading clears an imported report; a startup `--report` is loaded again.
This is a single-report viewer, not live multi-device monitoring or scheduling.

## Frontend development

Only UI maintainers need Node.js 22.12+:

```bash
cd frontend
npm ci
npm test
npm run build
```

Use `npm run dev` for development. Build output in `src/omnismi/dashboard/static`
is committed and ships with the wheel. The existing `docs/assets/OMNIsmi.svg`
is used for branding and included in source distributions. CI checks report
semantics, scoped module evidence, command generation, local HTTP boundaries,
core-only installation and reproducible assets. Passing software CI does not
replace real-device validation.
