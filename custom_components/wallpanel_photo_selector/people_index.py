"""Read optional Immich person mappings and report matching diagnostics."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)
MAX_INDEX_BYTES = 8 * 1024 * 1024


def load_people_index_diagnostics(
    root: Path, photos: dict[str, dict[str, Any]]
) -> tuple[dict[str, list[str]], dict[str, Any]]:
    """Return matched people and counts, without exposing private names in sensors."""
    path = root / "immich-people.json"
    diagnostics = {
        "status": "missing", "entries": 0, "matched": 0,
        "unmatched": 0, "error": None,
    }
    if not path.is_file():
        return {}, diagnostics
    try:
        if path.stat().st_size > MAX_INDEX_BYTES:
            raise ValueError("Immich people index exceeds 8 MiB")
        with path.open("r", encoding="utf-8-sig") as file:
            raw = json.load(file)
        if not isinstance(raw, dict):
            raise ValueError("Immich people index must be a JSON object")
    except (OSError, ValueError) as error:
        diagnostics.update(status="error", error=str(error))
        _LOGGER.warning("Could not read Immich people index %s: %s", path, error)
        return {}, diagnostics

    found = {}
    for relative, names in raw.items():
        if not isinstance(relative, str) or not isinstance(names, list):
            continue
        clean = list(dict.fromkeys(
            name.strip() for name in names if isinstance(name, str) and name.strip()
        ))
        if not clean:
            continue
        diagnostics["entries"] += 1
        if relative in photos:
            found[relative] = clean
    diagnostics["matched"] = len(found)
    diagnostics["unmatched"] = diagnostics["entries"] - len(found)
    diagnostics["status"] = "loaded"
    return found, diagnostics


def load_people_index(root: Path, photos: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """Backward-compatible people index reader."""
    return load_people_index_diagnostics(root, photos)[0]
