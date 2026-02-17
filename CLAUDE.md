# Omnismi - Unified GPU Monitoring and Observability Layer

## Project Overview

Omnismi provides a unified API for GPU monitoring across different hardware vendors. Users no longer need to call vendor-specific libraries (pynvml, amdsmi) directly - instead, they use omnismi to detect and query GPU information in a vendor-agnostic way.

## Architecture

```
omnismi/
├── src/omnismi/           # Main package
│   ├── __init__.py        # Public API exports
│   ├── types.py           # Type definitions (GPUInfo, GPUMetrics)
│   ├── detection.py       # Driver version detection
│   ├── installer.py       # Auto-install logic
│   ├── imports.py         # Lazy import utilities
│   ├── core/              # Core abstractions
│   │   ├── detector.py    # GPU detection logic
│   │   └── device.py      # GPU device abstraction
│   ├── vendors/           # Vendor-specific implementations
│   │   ├── nvidia/        # NVIDIA GPU support (pynvml)
│   │   ├── amd/           # AMD GPU support (amdsmi)
│   │   └── base.py        # Base vendor interface
│   └── cli/               # CLI tool
├── tests/                 # Test suite
├── docs/                  # Documentation
└── examples/              # Usage examples
```

## Installation

```bash
# Install with uv
uv pip install omnismi

# Or with pip
pip install omnismi

# Install with specific vendor support
uv pip install omnismi[nvidia]   # NVIDIA only
uv pip install omnismi[amd]      # AMD only
uv pip install omnismi[all]      # All vendors

# Auto-detect and install
omnismi-install install auto
```

## Key Features

1. **Optional Dependencies**: No mandatory dependencies - install only what you need
2. **Lazy Import**: Graceful handling of missing vendor libraries
3. **Driver Detection**: Automatic detection of CUDA/ROCm versions
4. **Version Compatibility**: API compatibility mapping for different driver versions

## Dependencies

- **Optional**: pynvml (NVIDIA), amdsmi (AMD)
- **Development**: pytest, mypy, black, isort, ruff

## Common Commands

```bash
# Install in development mode
pip install -e ".[dev]"

# Or with uv
uv pip install -e ".[dev]"

# Run tests
pytest

# Run a specific test
pytest tests/test_detector.py::test_detect_nvidia

# Type checking
mypy src/

# Formatting
black src/ tests/
isort src/ tests/

# Linting
ruff check src/ tests/

# Run CLI
omnismi --help
omnismi list
omnismi monitor

# Detect hardware
omnismi-install detect

# Auto-install dependencies
omnismi-install install auto
```

## CLI Commands

- `omnismi list` - List all available GPUs
- `omnismi monitor` - Real-time GPU monitoring
- `omnismi info <gpu_id>` - Detailed GPU information
- `omnismi-install detect` - Detect GPU hardware and drivers
- `omnismi-install install [auto|nvidia|amd|all]` - Install dependencies

## Public API (src/omnismi/__init__.py)

```python
from omnismi import detect_gpus, get_gpu, list_gpus
from omnismi.types import GPUInfo, GPUMetrics

# Driver detection
from omnismi import detection
cuda_info = detection.detect_cuda()
rocm_info = detection.detect_rocm()

# Auto-install
from omnismi import installer
installer.install_auto()
installer.check_installed()
```

## Extension Points

To add support for a new GPU vendor:
1. Create `src/omnismi/vendors/<vendor>/` module
2. Implement `BaseVendor` interface from `vendors/base.py`
3. Vendor is auto-registered via lazy import if library is available
