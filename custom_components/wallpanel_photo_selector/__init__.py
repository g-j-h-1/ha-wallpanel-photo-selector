"""WallPanel Photo Selector integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api, panel_custom, frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, DEFAULT_MEDIA_PATH, DEFAULT_SCAN_INTERVAL, PLATFORMS
from .scanner import scan_photo_directory
from .recognition import setup_recognition

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1
WS_TYPE = f"{DOMAIN}/photos"
WS_LIBRARY = f"{DOMAIN}/library"
PANEL_PATH = "wallpanel-photo-library"


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



@websocket_api.websocket_command({vol.Required("type"): WS_LIBRARY})
@websocket_api.async_response
async def websocket_photo_library(hass: HomeAssistant, connection, msg) -> None:
    """Return indexed filenames and scan errors for the read-only library browser."""
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        connection.send_result(msg["id"], {"photos": [], "errors": [], "scan_status": "unavailable"})
        return
    data = next(iter(entries.values()))
    summary = data.get("last_summary") or {}
    connection.send_result(msg["id"], {
        "photos": [
            {"path": item["path"], "rating": item.get("rating", 0),
             "orientation": item.get("orientation", "unknown"),
             "issues": item.get("metadata_issues", [])}
            for item in sorted(data["photos"].values(), key=lambda p: p["path"].casefold())
        ],
        "errors": summary.get("exceptions", []),
        "scan_status": data.get("scan_status"),
        "last_scan": data.get("last_scan"),
        "scan_error": data.get("scan_error"),
        "unreadable": summary.get("unreadable", 0),
    })

async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register WebSocket API."""
    websocket_api.async_register_command(hass, websocket_get_photos)
    websocket_api.async_register_command(hass, websocket_photo_library)
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            "/wallpanel-photo-selector/photo-library.js",
            str(Path(__file__).parent / "photo-library.js"),
            cache_headers=False,
        )
    ])
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up scanner and diagnostic entities."""
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_PATH,
        webcomponent_name="wallpanel-photo-library",
        js_url="/wallpanel-photo-selector/photo-library.js",
        sidebar_title="Photo Library",
        sidebar_icon="mdi:image-multiple",
        require_admin=True,
    )
    media_path = Path(entry.options.get("media_path", entry.data.get("media_path", DEFAULT_MEDIA_PATH))).resolve()
    interval = int(entry.options.get("scan_interval", entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)))
    store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}")
    cached = await store.async_load() or {"photos": {}, "last_scan": None, "last_summary": None}
    data = {
        "media_path": str(media_path), "scan_interval": interval,
        "photos": cached.get("photos", {}), "last_scan": cached.get("last_scan"),
        "last_summary": cached.get("last_summary"), "scan_status": "starting",
        "scan_error": None, "store": store, "lock": asyncio.Lock(),
        "scan_task": None, "scan": None, "next_scan": None, "scheduler_active": False,
    }
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data
    setup_recognition(hass, entry, data)
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _scan(_now=None) -> None:
        async with data["lock"]:
            data["scan_status"] = "scanning"
            _LOGGER.debug("Photo Selector scan started")
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

    # Register a Home Assistant interval listener rather than relying on a
    # perpetual sleeping task. HA owns the listener and removes it on unload.
    def _schedule_scan(_now=None) -> None:
        task = data.get("scan_task")
        if task is not None and not task.done():
            _LOGGER.debug("Photo Selector scan already running; skipping tick")
            return
        data["next_scan"] = (
            datetime.now(timezone.utc) + timedelta(minutes=interval)
        ).isoformat()
        data["scan_task"] = hass.async_create_task(
            _scan(), "WallPanel Photo Selector scan"
        )
        async_dispatcher_send(hass, f"{DOMAIN}_updated_{entry.entry_id}")

    unsubscribe = async_track_time_interval(
        hass, _schedule_scan, timedelta(minutes=interval)
    )
    entry.async_on_unload(unsubscribe)
    data["scheduler_active"] = True
    data["scan"] = _scan
    _schedule_scan()  # Initial scan; recurring scans follow HA's interval timer.
    _LOGGER.info("Photo Selector scheduled scans every %s minutes", interval)
    return True


async def _options_updated(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload integration and diagnostic entities."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False
    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if data and data.get("scan_task"):
        data["scan_task"].cancel()
    if not hass.data.get(DOMAIN):
        hass.data.pop(DOMAIN, None)
        frontend.async_remove_panel(hass, PANEL_PATH)
    return unload_ok
