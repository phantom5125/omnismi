# Alibaba / T-Head PPU adapter

Status: experimental PPU-SMI adapter implemented and registered; fixture-tested,
not hardware-validated. Initial metrics coverage is memory only.

## Available now

Install the vendor's SAIL/KMD tooling separately and make `ppu-smi` available on
PATH. Core Omnismi adds no SDK dependency or installer. Existing Python APIs and
`omnismi --vendor alibaba` / `omnismi doctor --vendor alibaba` discover physical
PPUs through an explicit CSV query of index, name, UUID, PCI address, driver,
total memory and used memory. MiB is converted to bytes. Unknown fields remain
None; temperature, power, activity and clocks are not yet queried.

The adapter queries at most once per 0.5 seconds on demand, with a 5-second timeout
and 1-MiB command output budget. It uses no shell, control/reset flags or background
sampler. UUID/PCI identity prevents reused indexes silently replacing devices.
Missing tools remain unavailable; malformed output and failed commands remain errors.

Source: [SAIL PPU-SMI manual, SDK v2.1.1](https://developer.t-head.cn/docs_center/doc_detail/index.html?projectId=39&chapterId=221),
reviewed 2026-09-22, sections 3.2 and 3.2.1. The official manual identifies HGML as
the underlying management library and documents CSV/nounits and the selected
fields. This implementation uses that documented CLI boundary, not an invented HGML ABI.

Limitations: physical management visibility, not verified process-runtime visibility;
MIG children, CUDA-compatible duplicate discovery, other telemetry, native HGML
bindings and real-device parity remain unvalidated. No card is marked verified.

Official references for the next diagnostic increment:
- [PPU XID overview](https://developer.t-head.cn/docs_center/doc_detail/index.html?projectId=38&chapterId=181)
- [PPU001 XID table](https://developer.t-head.cn/docs_center/doc_detail/index.html?projectId=38&chapterId=182)
- [PPU0015 XID table](https://developer.t-head.cn/docs_center/doc_detail/index.html?projectId=38&chapterId=183)
- [ECC handling](https://developer.t-head.cn/docs_center/doc_detail/index.html?projectId=38&chapterId=184)

These tables are generation-specific and are not yet included in the decoder.
The source index was retrieved from the site's public document API after the
initial HTML-only fetch could not render the dynamic site.
Target SKU and SDK version await confirmation. Use the Alibaba PPU family as the
provisional scope; the SDK guide's example SKU is not a hardware support promise.

## Verified starting point

Official source `alibaba-ppu-sdk` in `sources.json` documents `ppu-smi`, `ppu-smi -q`
and `asys status --ppu-env`. This identifies a practical discovery path; it does
not establish a stable NVML ABI or NVIDIA-compatible error semantics. Verify a
machine-readable output mode or SDK management ABI before selecting the collector.

## Implementation sequence

1. Obtain target SKU, installed SDK/driver versions, management SDK documentation,
   header/API signatures, `ppu-smi --help` and anonymized device/query samples.
   Record output format/version and distribution permissions for test fixtures.
2. `backends/alibaba_ppu.py`: optional lazy adapter, vendor `alibaba`, accelerator
   kind `ppu` in the richer report; retain the existing GPU API for compatibility.
   Prefer an officially documented structured interface. If only text is available,
   use an explicit versioned parser with unknown-format errors, never column guessing.
3. Inventory: identity, model, driver, total memory and PCI identity. Metrics:
   documented memory usage, temperature, power and activity, with verified units
   and semantics. Unsupported fields are None with a capability reason.
4. Register the backend, update VendorName and all CLI filters/diagnostic backend
   metadata. Check existing visibility/reporting assumptions; do not infer PPU
   selection semantics from CUDA environment variables without verification.
5. No-SDK and fixture tests; real-device parity against `ppu-smi`, then compatibility
   matrix entry. Add benchmark/topology/error capabilities in later commits only
   when their APIs and hardware evidence are available.

## Boundaries and acceptance

Core install has no PPU dependency, driver download or runtime installation.
Library imports do not launch subprocesses. Collectors have timeouts, no shell,
structured errors and no reset/control operations. Device enumeration cannot
claim support solely from a PCI device number or generic CUDA compatibility.

Test missing SDK/tool, old/unknown versions, multi-device identity, unavailable
metrics, malformed output, timeout, permission denial and exact unit conversion.
Hardware evidence includes model, OS, driver/SDK, tool output and normalized report.
Until then label only fixture-tested/experimental, never hardware-verified.

## User-confirmed SDK direction

Use T-Head SAIL SDK as the primary software stack. The official developer-center
search index lists runtime/driver APIs, KMD ECC/XID references and interconnect
documentation. Retrieve and pin those specific manuals before coding bindings or
rules; the index is not an ABI reference. The older Alibaba Cloud SDK guide above
is supplementary. PPU XID codes must use vendor `alibaba`, never inherit NVIDIA
Xid rules merely because the namespace name matches.
