"""CLI for omnismi."""

import argparse
import sys
import time
from typing import Optional

from omnismi import detect_gpus, get_gpu
from omnismi.types import GPUInfo


def list_gpus_command(args) -> int:
    """List all available GPUs."""
    gpus = detect_gpus()

    if not gpus:
        print("No GPUs detected.")
        return 0

    print(f"Found {len(gpus)} GPU(s):\n")
    for gpu in gpus:
        memory_str = _format_memory(gpu.memory_total) if gpu.memory_total else "N/A"
        print(f"  [{gpu.id}] {gpu.name}")
        print(f"      Vendor: {gpu.vendor}")
        print(f"      Memory: {memory_str}")
        print(f"      Driver: {gpu.driver_version or 'N/A'}")
        print()

    return 0


def info_command(args) -> int:
    """Show detailed info for a specific GPU."""
    gpu = get_gpu(args.gpu_id)

    if not gpu:
        print(f"Error: GPU {args.gpu_id} not found.")
        return 1

    print(f"GPU {gpu.id}: {gpu.name}")
    print(f"  Vendor: {gpu.vendor}")
    print(f"  Memory Total: {_format_memory(gpu.memory_total) if gpu.memory_total else 'N/A'}")

    metrics = gpu.get_metrics()
    if metrics:
        print(f"  Memory Used: {_format_memory(metrics.memory_used) if metrics.memory_used else 'N/A'}")
        print(f"  Memory Free: {_format_memory(metrics.memory_free) if metrics.memory_free else 'N/A'}")
        print(f"  GPU Utilization: {metrics.utilization_gpu if metrics.utilization_gpu is not None else 'N/A'}%")
        print(f"  Memory Utilization: {metrics.utilization_memory if metrics.utilization_memory is not None else 'N/A'}%")
        print(f"  Temperature: {metrics.temperature if metrics.temperature is not None else 'N/A'}°C")
        print(f"  Power Usage: {metrics.power_usage if metrics.power_usage is not None else 'N/A'}W")
        print(f"  Clock Speed: {metrics.clock_speed if metrics.clock_speed is not None else 'N/A'} MHz")

    return 0


def monitor_command(args) -> int:
    """Monitor GPUs in real-time."""
    gpus = detect_gpus()

    if not gpus:
        print("No GPUs detected.")
        return 1

    interval = args.interval
    try:
        while True:
            _clear_screen()
            print(f"GPU Monitor (refresh: {interval}s)\n")
            print("-" * 80)

            for gpu in gpus:
                metrics = gpu.get_metrics()
                if metrics:
                    mem_used = _format_memory(metrics.memory_used) if metrics.memory_used else "N/A"
                    mem_total = _format_memory(gpu.memory_total) if gpu.memory_total else "N/A"
                    util = f"{metrics.utilization_gpu}%" if metrics.utilization_gpu is not None else "N/A"
                    temp = f"{metrics.temperature}°C" if metrics.temperature is not None else "N/A"
                    power = f"{metrics.power_usage}W" if metrics.power_usage is not None else "N/A"

                    print(f"GPU {gpu.id}: {gpu.name}")
                    print(f"  Util: {util} | Temp: {temp} | Power: {power}")
                    print(f"  Memory: {mem_used} / {mem_total}")
                    print("-" * 80)

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
        return 0


def _format_memory(bytes_value: Optional[int]) -> str:
    """Format memory in bytes to human-readable string."""
    if bytes_value is None:
        return "N/A"

    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f}{unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f}PB"


def _clear_screen():
    """Clear the terminal screen."""
    import os
    os.system("cls" if os.name == "nt" else "clear")


def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="omnismi",
        description="Unified GPU Monitoring and Observability Layer"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list command
    list_parser = subparsers.add_parser("list", help="List all available GPUs")

    # info command
    info_parser = subparsers.add_parser("info", help="Show detailed GPU information")
    info_parser.add_argument("gpu_id", type=int, help="GPU ID to query")

    # monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Monitor GPUs in real-time")
    monitor_parser.add_argument(
        "--interval", "-i", type=float, default=2.0,
        help="Refresh interval in seconds (default: 2.0)"
    )

    args = parser.parse_args()

    if args.command == "list":
        return list_gpus_command(args)
    elif args.command == "info":
        return info_command(args)
    elif args.command == "monitor":
        return monitor_command(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
