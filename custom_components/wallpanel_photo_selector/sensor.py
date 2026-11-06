"""Diagnostic sensors for WallPanel Photo Selector."""

from __future__ import annotations

from datetime import datetime
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

METRICS = (
    ("scan_status", "Scan status", "mdi:database-check", None),
    ("last_scan", "Last scan", "mdi:clock-check", SensorDeviceClass.TIMESTAMP),
    ("total", "Photos indexed", "mdi:image-multiple", None),
    ("discovered", "JPEG files detected", "mdi:file-image", None),
    ("landscape", "Landscape photos", "mdi:panorama", None),
    ("portrait", "Portrait photos", "mdi:crop-portrait", None),
    ("square", "Square photos", "mdi:square", None),
    ("unknown", "Unknown orientation", "mdi:image-question", None),
    ("unrated", "Unrated photos", "mdi:star-off", None),
    ("rating_1", "1-star photos", "mdi:star", None),
    ("rating_2", "2-star photos", "mdi:star", None),
    ("rating_3", "3-star photos", "mdi:star", None),
    ("rating_4", "4-star photos", "mdi:star", None),
    ("rating_5", "5-star photos", "mdi:star", None),
    ("unreadable", "Unreadable JPEGs", "mdi:alert-circle", None),
    ("exceptions", "Metadata exceptions", "mdi:file-alert", None),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create diagnostic sensors."""
    async_add_entities(PhotoSelectorSensor(hass, entry, key, name, icon, device_class)
                       for key, name, icon, device_class in METRICS)


class PhotoSelectorSensor(SensorEntity):
    """Expose scanner health and photo-library breakdown."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass, entry, key, name, icon, device_class):
        self.hass = hass
        self.entry = entry
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_extra_state_attributes = {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="WallPanel Photo Selector",
            manufacturer="WallPanel",
            model="Photo library scanner",
        )

    async def async_added_to_hass(self):
        """Subscribe to completed scans."""
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, f"{DOMAIN}_updated_{self.entry.entry_id}", self._refresh
        ))

    def _snapshot(self):
        data = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id, {})
        summary = data.get("last_summary") or {}
        photos = data.get("photos", {})
        ratings = summary.get("ratings", {})
        orientations = summary.get("orientations", {})
        return data, summary, photos, ratings, orientations

    @property
    def native_value(self):
        data, summary, photos, ratings, orientations = self._snapshot()
        if self.key == "scan_status":
            return data.get("scan_status", "unknown")
        if self.key == "last_scan":
            value = data.get("last_scan")
            return datetime.fromisoformat(value) if value else None
        if self.key == "total":
            return len(photos)
        if self.key == "discovered":
            return summary.get("discovered", 0)
        if self.key in ("landscape", "portrait", "square", "unknown"):
            return orientations.get(self.key, 0)
        if self.key == "exceptions":
            return summary.get("exception_count", 0)
        if self.key == "unreadable":
            return summary.get("unreadable", 0)
        if self.key == "unrated":
            return ratings.get("0", 0)
        if self.key.startswith("rating_"):
            return ratings.get(self.key.split("_", 1)[1], 0)
        return None

    @property
    def extra_state_attributes(self):
        data, summary, photos, ratings, orientations = self._snapshot()
        return {
            "media_path": data.get("media_path"),
            "scan_interval_minutes": data.get("scan_interval"),
            "last_scan_status": data.get("scan_status"),
            "last_scan_error": data.get("scan_error"),
            "added": summary.get("added", 0),
            "modified": summary.get("modified", 0),
            "deleted": summary.get("deleted", 0),
            "unchanged": summary.get("unchanged", 0),
            "ratings": ratings,
            "orientations": orientations,
            "exception_count": summary.get("exception_count", 0),
            "exception_examples": (summary.get("exceptions") or [])[:20],
        }

    def _refresh(self):
        self.async_write_ha_state()
