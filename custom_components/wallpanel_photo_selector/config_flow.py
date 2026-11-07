"""Config flow for WallPanel Photo Selector."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, DEFAULT_MEDIA_PATH, DEFAULT_SCAN_INTERVAL, MIN_SCAN_INTERVAL, MAX_SCAN_INTERVAL


class WallPanelPhotoSelectorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PhotoSelectorOptionsFlow()

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            path = Path(user_input["media_path"]).expanduser().resolve()
            media_root = Path("/media").resolve()
            if path == media_root or not path.is_relative_to(media_root):
                errors["media_path"] = "invalid_path"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="WallPanel Photo Selector",
                    data={**user_input, "media_path": str(path)},
                )

        schema = vol.Schema({
            vol.Required("media_path", default=DEFAULT_MEDIA_PATH): str,
            vol.Required("scan_interval", default=DEFAULT_SCAN_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
            ),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class PhotoSelectorOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            url = user_input.get("recognition_url", "").strip().rstrip("/")
            user_input["recognition_url"] = url
            if url:
                try:
                    parsed = urlsplit(url)
                    port = parsed.port
                    valid = (parsed.scheme in {"http", "https"} and parsed.hostname
                             and not any((parsed.username, parsed.password, parsed.query, parsed.fragment, parsed.path))
                             and (port is None or 1 <= port <= 65535))
                except ValueError:
                    valid = False
                if not valid:
                    errors["recognition_url"] = "invalid_url"
                if len(user_input.get("recognition_token", "")) < 32:
                    errors["recognition_token"] = "invalid_token"
                if not user_input.get("recognition_camera") or not user_input.get("recognition_person"):
                    errors["base"] = "missing_entities"
            if not errors:
                return self.async_create_entry(title="", data={**self.config_entry.options, **user_input})
        defaults = {**self.config_entry.options, **(user_input or {})}
        schema = vol.Schema({
            vol.Optional("recognition_url", default=defaults.get("recognition_url", "")): str,
            vol.Optional("recognition_token", default=defaults.get("recognition_token", "")): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            vol.Optional("recognition_camera", description={"suggested_value": defaults.get("recognition_camera")}): selector.EntitySelector(selector.EntitySelectorConfig(domain="camera")),
            vol.Optional("recognition_person", description={"suggested_value": defaults.get("recognition_person")}): selector.EntitySelector(selector.EntitySelectorConfig(domain="binary_sensor")),
        })
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
