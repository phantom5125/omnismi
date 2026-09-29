"""Load the reviewed, packaged error catalog, without fetching remote content."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


def load_catalog() -> dict[str, Any]:
    """Read a fresh copy, so callers cannot mutate subsequent lookup results."""
    catalog = json.loads(
        files("omnismi.diagnostics").joinpath("catalog.json").read_text("utf-8")
    )
    if catalog["schema_version"] != 1:
        raise ValueError("Unsupported diagnostics catalog schema")
    sources = {item["id"] for item in catalog["sources"]}
    keys = set()
    for rule in catalog["rules"]:
        key = (rule["vendor"], rule["namespace"], rule["code"])
        if key in keys or not set(rule["source_ids"]).issubset(sources):
            raise ValueError("Invalid diagnostics catalog references")
        keys.add(key)
    return catalog
