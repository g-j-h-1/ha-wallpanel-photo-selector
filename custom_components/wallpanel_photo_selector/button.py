"""Manual rescan button for WallPanel Photo Selector."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the rescan button on the integration's device."""
    async_add_entities([PhotoSelectorRescanButton(hass, entry)])


class PhotoSelectorRescanButton(ButtonEntity):
    """Request an immediate scan of the configured photo directory."""

    _attr_has_entity_name = True
    _attr_name = "Rescan photos"
    _attr_icon = "mdi:refresh"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_rescan"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="WallPanel Photo Selector",
            manufacturer="WallPanel",
            model="Photo library scanner",
        )

    async def async_press(self) -> None:
        """Start a scan, serialized with any automatic scan."""
        data = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id)
        if data and data.get("scan"):
            await data["scan"]()
