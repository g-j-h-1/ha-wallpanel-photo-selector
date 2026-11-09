"""Read an optional Immich filename-to-names export alongside the photo library."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)
MAX_INDEX_BYTES = 8 * 1024 * 1024


def load_people_index(root: Path, photos: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """Return people for indexed JPEGs; invalid or missing JSON is nonfatal."""
    path = root / "immich-people.json"
    try:
        if not path.is_file():
            return {}
        if path.stat().st_size > MAX_INDEX_BYTES:
            raise ValueError("Immich people index exceeds 8 MiB")
        with path.open("r", encoding="utf-8-sig") as file:
            raw = json.load(file)
        if not isinstance(raw, dict):
            raise ValueError("Immich people index must be a JSON object")
    except (OSError, ValueError) as error:
        _LOGGER.warning("Could not read Immich people index %s: %s", path, error)
        return {}

    found = {}
    for relative, names in raw.items():
        if not isinstance(relative, str) or relative not in photos or not isinstance(names, list):
            continue
        clean = list(dict.fromkeys(
            name.strip() for name in names if isinstance(name, str) and name.strip()
        ))
        if clean:
            found[relative] = clean
    return found
