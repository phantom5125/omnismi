# Omnismi

Unified GPU Monitoring and Observability Layer.

## Overview

Omnismi provides a unified API for GPU monitoring across different hardware vendors. Users no longer need to call vendor-specific libraries (pynvml, amdsmi) directly - instead, they use omnismi to detect and query GPU information in a vendor-agnostic way.

## Supported Vendors

- NVIDIA (via pynvml)
- AMD (via amdsmi)

## Installation

### Using uv (Recommended)

```bash
# Install base package (no dependencies required)
uv pip install omnismi

# Install with NVIDIA support
uv pip install omnismi[nvidia]

# Install with AMD support
uv pip install omnismi[amd]

# Install with all vendor support
uv pip install omnismi[all]

# Auto-detect hardware and install appropriate dependencies
omnismi-install install auto
```

### Using pip

```bash
pip install omnismi
pip install omnismi[nvidia]  # NVIDIA only
pip install omnismi[amd]     # AMD only
pip install omnismi[all]     # All vendors
```

## Quick Start

```python
from omnismi import detect_gpus, list_gpus, get_gpu

# Detect all GPUs
gpus = detect_gpus()
print(f"Found {len(gpus)} GPU(s)")

# List GPUs
for gpu in list_gpus():
    print(f"GPU {gpu.id}: {gpu.name} ({gpu.vendor})")

# Get specific GPU and its metrics
gpu = get_gpu(0)
metrics = gpu.get_metrics()
print(f"Utilization: {metrics.utilization_gpu}%")
print(f"Memory Used: {metrics.memory_used} bytes")
```

## CLI Usage

```bash
# List all GPUs
omnismi list

# Get detailed GPU info
omnismi info 0

# Monitor GPUs in real-time
omnismi monitor
omnismi monitor --interval 5

# Detect hardware and drivers
omnismi-install detect

# Auto-install dependencies based on hardware
omnismi-install install auto
```

## Driver Detection

Omnismi can detect your CUDA/ROCm driver versions:

```python
from omnismi import detection

# Detect NVIDIA
cuda_info = detection.detect_cuda()
if cuda_info:
    print(f"CUDA Version: {cuda_info.cuda_version}")
    print(f"Driver Version: {cuda_info.driver_version}")

# Detect AMD ROCm
rocm_info = detection.detect_rocm()
if rocm_info:
    print(f"ROCm Version: {rocm_info.rocmm_version}")
    print(f"HIP Version: {rocm_info.hip_version}")
```

## Auto-Installation

If you don't know which GPU you have, use auto-detection:

```bash
# This will:
# 1. Detect your GPU hardware
# 2. Detect driver versions
# 3. Install appropriate dependencies
omnismi-install install auto
```

Or programmatically:

```python
from omnismi import installer

# Check what's installed
status = installer.check_installed()
print(f"NVIDIA: {status['nvidia']}")
print(f"AMD: {status['amd']}")

# Auto-install based on hardware
installer.install_auto()
```

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/

# Formatting
black src/ tests/
```

## License

MIT
