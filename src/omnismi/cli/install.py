"""CLI for omnismi installation."""

import argparse
import sys

from omnismi import detection, installer


def install_command(args) -> int:
    """Install omnismi dependencies."""
    if args.vendor == "auto":
        print("Auto-detecting hardware and installing dependencies...")
        success = installer.install_auto()
        if success:
            print("Dependencies installed successfully!")
            return 0
        else:
            print("No GPU hardware detected or installation failed.")
            print(installer.suggest_installation())
            return 1

    elif args.vendor == "all":
        print("Installing all vendor dependencies...")
        success = installer.install_all()
        if success:
            print("All dependencies installed successfully!")
            return 0
        return 1

    elif args.vendor == "nvidia":
        print("Installing NVIDIA dependencies (pynvml)...")
        if installer.install_nvidia():
            print("NVIDIA dependencies installed successfully!")
            return 0
        print("Failed to install NVIDIA dependencies.")
        return 1

    elif args.vendor == "amd":
        print("Installing AMD dependencies (amdsmi)...")
        if installer.install_amd():
            print("AMD dependencies installed successfully!")
            return 0
        print("Failed to install AMD dependencies.")
        return 1

    return 0


def detect_command(args) -> int:
    """Detect GPU hardware and driver information."""
    print("Detecting GPU hardware...\n")

    # Check NVIDIA
    cuda_info = detection.detect_cuda()
    if cuda_info:
        print(f"NVIDIA:")
        print(f"  Driver Version: {cuda_info.driver_version}")
        if cuda_info.cuda_version:
            print(f"  CUDA Version: {cuda_info.cuda_version}")
        print(f"  GPU Count: {cuda_info.device_count}")
    else:
        print("NVIDIA: No NVIDIA GPUs detected")

    print()

    # Check AMD
    rocm_info = detection.detect_rocm()
    if rocm_info:
        print(f"AMD ROCm:")
        print(f"  Driver Version: {rocm_info.driver_version}")
        if rocm_info.rocmm_version:
            print(f"  ROCm Version: {rocm_info.rocmm_version}")
        if rocm_info.hip_version:
            print(f"  HIP Version: {rocm_info.hip_version}")
    else:
        print("AMD ROCm: No ROCm-capable AMD GPUs detected")

    print()

    # Check installed packages
    status = installer.check_installed()
    print("Installed packages:")
    print(f"  pynvml: {'Installed' if status['nvidia'] else 'Not installed'}")
    print(f"  amdsmi: {'Installed' if status['amd'] else 'Not installed'}")

    if not cuda_info and not rocm_info:
        print("\nNo GPU hardware detected.")
        print(installer.suggest_installation())

    return 0


def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="omnismi-install",
        description="Install and detect GPU dependencies for omnismi"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # install command
    install_parser = subparsers.add_parser("install", help="Install GPU dependencies")
    install_parser.add_argument(
        "vendor",
        nargs="?",
        default="auto",
        choices=["auto", "all", "nvidia", "amd"],
        help="Which vendor to install (default: auto)"
    )

    # detect command
    detect_parser = subparsers.add_parser("detect", help="Detect GPU hardware and drivers")

    args = parser.parse_args()

    if args.command == "install":
        return install_command(args)
    elif args.command == "detect":
        return detect_command(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
