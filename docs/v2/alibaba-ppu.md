# Alibaba / T-Head PPU adapter

Status: research and implementation contract; adapter not implemented or registered.
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
