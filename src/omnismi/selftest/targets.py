"""Reviewed target presets, shared by the CLI and bundled dashboard."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=1)
def target_catalog():
    return json.loads(files("omnismi.selftest").joinpath("targets.json").read_text())


def target_profile(identifier):
    for target in target_catalog()["targets"]:
        if target["id"] == identifier:
            return target
    raise ValueError(f"unknown target: {identifier}")


def matches_target(identifier, identity):
    target = target_profile(identifier)
    return identity.get("vendor") == target["vendor"] and bool(
        re.search(target["name_pattern"], str(identity.get("name", "")), re.IGNORECASE)
    )
