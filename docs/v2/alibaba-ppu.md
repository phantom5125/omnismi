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
HGML is accessed through the vendor's PPU-SMI boundary. Active SAIL compute probes
remain INCONCLUSIVE until the runtime/API identity boundary is verified; a generic
CUDA-compatible import is insufficient to select a PPU safely.

Primary references:

- [PPU-SMI v2.1.1 manual](https://developer.t-head.cn/docs_center/doc_detail/index.html?projectId=39&chapterId=221)
- [PPU001 XID table](https://developer.t-head.cn/docs_center/doc_detail/index.html?projectId=38&chapterId=182)
- [PPU0015 XID table](https://developer.t-head.cn/docs_center/doc_detail/index.html?projectId=38&chapterId=183)

Source hashes/review dates are packaged in the offline catalog. No driver/SDK
installer or complete proprietary manual is bundled. Real-device parity, installed
SDK versions, runtime visibility and exact target card remain validation inputs.
