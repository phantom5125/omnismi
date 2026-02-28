## Summary

Describe what changed and why.

## Validation

- [ ] `PYTHONPATH=src pytest -q` passed locally, or I explained why not.
- [ ] If applicable, I ran `PYTHONPATH=src python -m omnismi.validation.parity --vendor <vendor> --samples 5`.

## Hardware Validation Matrix Checklist

- [ ] I stated whether this PR changes the hardware validation matrix.
- [ ] If I add or upgrade a `✅ Verified` model, I attached parity output and environment evidence.
- [ ] I updated `docs/compatibility.md` when a validation status changed.
- [ ] I explicitly preserved this statement where relevant: `🧪 Awaiting User Validation` does NOT mean unsupported.

## Hardware Evidence (required when adding/upgrading verified models)

- GPU model:
- Vendor:
- Driver/runtime versions:
- OS/kernel:
- Python version:
- Install extra:
- `pytest -q` result:
- Parity output summary:
- Minimal read script output summary:
