# Cambricon adapter

Status: research and implementation contract; adapter not implemented or registered.
Target MLU model, Neuware/CNDEV version and access to full SDK documentation are open.

## Verified starting point

Official source `cambricon-cndev` in `sources.json` is the CNDev developer manual
entry. Its SDK download flow requires enterprise access approval. The entry alone
does not establish C signatures, structure layout or supported output modes.
Use the actual versioned CNDEV headers and documentation before implementing FFI.
Do not invent a pip package, C ABI or management-tool JSON switch.

## Implementation sequence

1. Obtain model and driver/Neuware/CNDEV versions, management headers/manual,
   documented tool help and anonymized inventory/metrics output. Establish which
   official interface supports safe read-only use and its initialization lifecycle.
2. `backends/cambricon.py`: optional lazy adapter, vendor `cambricon`, accelerator
   kind `mlu` in the richer report; preserve the existing GPU API contract.
3. Implement documented inventory and metrics. Each FFI structure must match the
   verified SDK ABI including version fields and alignment; mock tests alone do
   not prove native safety. Use documented CLI fallback only with versioned parsing.
4. Normalize bytes, percent, Celsius, Watts and MHz; preserve missing fields as
   None and distinguish unsupported from unavailable. Track device identity
   independently of runtime index. Verify visibility controls from vendor docs.
5. Update registry, vendor types/filters, diagnostics metadata, docs and capability
   matrix. No-SDK operation stays quiet and functional. Add real-device parity
   before declaring hardware validation.

## Acceptance

Tests cover unavailable library, initialization failure, error return codes,
unsupported fields, unit conversions, multi-device identity and lifecycle cleanup.
Command-based collection has bounded execution and unknown-format handling.
Provide SDK-version fixtures and hardware evidence (model, OS, driver/runtime,
raw official readings and normalized reports). Avoid global process environment
changes. Do not download proprietary SDKs or register a nonfunctional placeholder.

Initial completion is discovery/metrics parity. Topology, error decoding and
benchmarks are separate capability gates requiring documented APIs and hardware
validation; lack of one capability must not hide a device from basic inventory.
