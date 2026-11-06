"""WallPanel Photo Selector integration."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import DOMAIN, DEFAULT_MEDIA_PATH, DEFAULT_SCAN_INTERVAL, PLATFORMS
from .scanner import scan_photo_directory

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1
WS_TYPE = f"{DOMAIN}/photos"


@websocket_api.websocket_command({vol.Required("type"): WS_TYPE})
@websocket_api.async_response
async def websocket_get_photos(hass: HomeAssistant, connection, msg) -> None:
    """Return indexed photo metadata to a WallPanel client."""
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        connection.send_result(msg["id"], {"photos": [], "last_scan": None})
        return
    data = next(iter(entries.values()))
    photos = [
        {"path": item["path"], "rating": item.get("rating", 0),
         "weight": max(1, int(item.get("rating", 0))),
         "orientation": item.get("orientation", "unknown")}
        for item in data["photos"].values()
    ]
    connection.send_result(msg["id"], {
        "photos": photos, "media_folder": Path(data["media_path"]).name,
        "last_scan": data.get("last_scan"),
    })


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register WebSocket API."""
    websocket_api.async_register_command(hass, websocket_get_photos)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up scanner and diagnostic entities."""
    media_path = Path(entry.options.get("media_path", entry.data.get("media_path", DEFAULT_MEDIA_PATH))).resolve()
    interval = int(entry.options.get("scan_interval", entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)))
    store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}")
    cached = await store.async_load() or {"photos": {}, "last_scan": None, "last_summary": None}
    data = {
        "media_path": str(media_path), "scan_interval": interval,
        "photos": cached.get("photos", {}), "last_scan": cached.get("last_scan"),
        "last_summary": cached.get("last_summary"), "scan_status": "starting",
        "scan_error": None, "store": store, "lock": asyncio.Lock(),
        "scan_task": None, "scan": None,
    }
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _scan(_now=None) -> None:
        async with data["lock"]:
            data["scan_status"] = "scanning"
            data["scan_error"] = None
            async_dispatcher_send(hass, f"{DOMAIN}_updated_{entry.entry_id}")
            try:
                photos, summary = await hass.async_add_executor_job(
                    scan_photo_directory, media_path, data["photos"]
                )
                data["photos"] = photos
                data["last_scan"] = summary["completed_at"]
                data["last_summary"] = summary
                data["scan_status"] = "success"
                data["scan_error"] = None
                await store.async_save({
                    "photos": photos, "last_scan": data["last_scan"],
                    "last_summary": summary,
                })
                _LOGGER.info(
                    "Photo scan complete: %s indexed from %s JPEG files; %s unreadable",
                    summary["found"], summary["discovered"], summary["unreadable"],
                )
            except Exception as err:
                data["scan_status"] = "error"
                data["scan_error"] = str(err)
                data["last_summary"] = {
                    "status": "error", "completed_at": None, "error": str(err),
                    "found": len(data["photos"]),
                }
                _LOGGER.exception("Unable to scan photo directory %s", media_path)
            async_dispatcher_send(hass, f"{DOMAIN}_updated_{entry.entry_id}")

    async def _scan_loop() -> None:
        # Run an initial scan, then schedule the next one after each completed scan.
        # Keeping this task in the config entry avoids a lost interval callback.
        while True:
            await _scan()
            await asyncio.sleep(interval * 60)

    data["scan"] = _scan
    data["scan_task"] = entry.async_create_background_task(
        hass, _scan_loop(), "WallPanel Photo Selector scheduled scan"
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload integration and diagnostic entities."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if data and data.get("scan_task"):
        data["scan_task"].cancel()
    if not hass.data.get(DOMAIN):
        hass.data.pop(DOMAIN, None)
    return unload_ok
