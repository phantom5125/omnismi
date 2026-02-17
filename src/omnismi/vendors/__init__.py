"""Vendor implementations for different GPU manufacturers."""

from omnismi.vendors.base import BaseVendor

# Registry of available vendor implementations
VENDORS: list[BaseVendor] = []


def register_vendor(vendor: BaseVendor) -> None:
    """Register a vendor implementation."""
    VENDORS.append(vendor)


def get_vendors() -> list[BaseVendor]:
    """Get all registered vendor implementations."""
    return VENDORS.copy()
