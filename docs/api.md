# API Reference

## Top-level API

::: omnismi
    options:
      show_root_heading: false
      members:
        - count
        - gpus
        - gpu
        - GPU
        - GPUInfo
        - GPUMetrics

## Validation Tool

Run parity checks manually:

```bash
python -m omnismi.validation.parity --vendor nvidia --samples 3
python -m omnismi.validation.parity --vendor amd --samples 3
```
