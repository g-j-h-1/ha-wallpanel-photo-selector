"""Incremental JPEG metadata scanner for the WallPanel photo library."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from typing import Any

IMAGE_SUFFIXES = {".jpg", ".jpeg"}
XMP_HEADER = b"http://ns.adobe.com/xap/1.0/\x00"
SOF_MARKERS = {
    0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
    0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
}


def _jpeg_metadata(path: Path, issues: list[str] | None = None) -> tuple[int | None, int | None, int]:
    """Return width, height and Lightroom XMP rating (0 means unrated)."""
    width = height = None
    rating = 0
    with path.open("rb") as image:
        if image.read(2) != b"\xff\xd8":
            raise ValueError("Not a JPEG file")
        while True:
            if image.read(1) != b"\xff":
                break
            marker_byte = image.read(1)
            while marker_byte == b"\xff":
                marker_byte = image.read(1)
            if not marker_byte:
                break
            marker = marker_byte[0]
            if marker in (0xD9, 0xDA):
                break
            if marker in (0x01, *range(0xD0, 0xD8)):
                continue
            length_bytes = image.read(2)
            if len(length_bytes) != 2:
                break
            segment_length = int.from_bytes(length_bytes, "big")
            if segment_length < 2:
                break
            payload_length = segment_length - 2
            if marker == 0xE1:
                payload = image.read(payload_length)
                if payload.startswith(XMP_HEADER):
                    packet = payload[len(XMP_HEADER):].rstrip(b"\x00")
                    rating = _extract_rating(packet) or 0
                    try:
                        ET.fromstring(packet)
                    except ET.ParseError:
                        rating = 0
                        if issues is not None:
                            issues.append("Malformed XMP metadata; assigned zero stars")
            elif marker in SOF_MARKERS:
                payload = image.read(payload_length)
                if len(payload) >= 5:
                    height = int.from_bytes(payload[1:3], "big")
                    width = int.from_bytes(payload[3:5], "big")
            else:
                image.seek(payload_length, 1)
    if not width or not height:
        raise ValueError("Missing or invalid JPEG dimensions")
    return width, height, rating


def _extract_rating(packet: bytes) -> int | None:
    """Read xmp:Rating from RDF attributes or element text."""
    try:
        root = ET.fromstring(packet)
    except ET.ParseError:
        match = re.search(rb'<(?:[A-Za-z0-9_-]+:)?Description\b[^>]*\bxmp:Rating=["\'](-?\d+)["\']', packet)
        return max(0, min(5, int(match.group(1)))) if match else None
    for element in root.iter():
        for key, value in element.attrib.items():
            if key.rsplit("}", 1)[-1] == "Rating":
                try:
                    return max(0, min(5, int(float(value))))
                except (TypeError, ValueError):
                    pass
        if element.tag.rsplit("}", 1)[-1] == "Rating" and element.text:
            try:
                return max(0, min(5, int(float(element.text.strip()))))
            except (TypeError, ValueError):
                pass
    return None


def scan_photo_directory(
    root: Path, previous: dict[str, dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Scan recursively and return indexed metadata plus a diagnostic summary."""
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Photo directory does not exist: {root}")

    current: dict[str, dict[str, Any]] = {}
    added = modified = unchanged = unreadable = discovered = 0
    exceptions: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        discovered += 1
        try:
            resolved_path = path.resolve(strict=True)
            if not resolved_path.is_relative_to(root) or not resolved_path.is_file():
                unreadable += 1
                exceptions.append({"path": path.relative_to(root).as_posix(), "reason": "File inaccessible or outside photo directory"})
                continue
            relative = path.relative_to(root).as_posix()
            stat = resolved_path.stat()
            old = previous.get(relative)
            if old and old.get("mtime_ns") == stat.st_mtime_ns and old.get("size") == stat.st_size:
                current[relative] = old
                for reason in old.get("metadata_issues", []):
                    exceptions.append({"path": relative, "reason": reason})
                unchanged += 1
                continue
            metadata_issues = []
            width, height, rating = _jpeg_metadata(resolved_path, metadata_issues)
            for reason in metadata_issues:
                exceptions.append({"path": relative, "reason": reason})
            if not width or not height:
                exceptions.append({"path": relative, "reason": "Image dimensions unavailable; assigned zero stars"})
                rating = 0
            current[relative] = {
                "path": relative, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
                "rating": rating,
                "orientation": (
                    "landscape" if width and height and width > height
                    else "portrait" if width and height and height > width
                    else "square" if width and height else "unknown"
                ),
                "width": width, "height": height, "weight": max(0, rating),
                "metadata_issues": metadata_issues,
            }
            if old is None:
                added += 1
            else:
                modified += 1
        except (OSError, ValueError) as error:
            exceptions.append({"path": path.relative_to(root).as_posix(), "reason": f"Unreadable image: {error}"})
            unreadable += 1
            continue

    deleted = len(set(previous) - set(current))
    ratings = {str(star): sum(1 for p in current.values() if p.get("rating", 0) == star) for star in range(6)}
    orientations = {kind: sum(1 for p in current.values() if p.get("orientation") == kind)
                    for kind in ("landscape", "portrait", "square", "unknown")}
    summary = {
        "status": "success", "found": len(current), "discovered": discovered,
        "added": added, "modified": modified, "deleted": deleted,
        "unchanged": unchanged, "unreadable": unreadable,
        "ratings": ratings, "orientations": orientations,
        "exceptions": exceptions, "exception_count": len(exceptions),
        "completed_at": datetime.now(timezone.utc).isoformat(), "error": None,
    }
    return current, summary
