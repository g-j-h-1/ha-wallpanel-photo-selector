"""Validate optional worker settings while preserving existing scanner options."""
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from custom_components.wallpanel_photo_selector.config_flow import PhotoSelectorOptionsFlow


class OptionsTests(unittest.IsolatedAsyncioTestCase):
    def flow(self):
        flow = PhotoSelectorOptionsFlow()
        flow.hass = MagicMock()
        flow.hass.config_entries.async_get_known_entry.return_value = SimpleNamespace(
            options={"media_path":"/media/custom", "scan_interval":30})
        flow.handler = "test"
        return flow

    async def test_saving_worker_preserves_existing_photo_path(self):
        result = await self.flow().async_step_init({
            "recognition_url":"http://worker:8099/", "recognition_token":"x"*32,
            "recognition_camera":"camera.portal", "recognition_person":"binary_sensor.portal",
        })
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"]["media_path"], "/media/custom")
        self.assertEqual(result["data"]["scan_interval"], 30)

    async def test_bad_origins_show_form_errors(self):
        for url in ["file:///tmp/worker", "http://worker/match", "http://user:pass@worker", "http://[broken", "http://worker:bad"]:
            result = await self.flow().async_step_init({
                "recognition_url":url, "recognition_token":"x"*32,
                "recognition_camera":"camera.portal", "recognition_person":"binary_sensor.portal",
            })
            self.assertEqual(result["errors"]["recognition_url"], "invalid_url")

    async def test_blank_url_disables_optional_service(self):
        result = await self.flow().async_step_init({"recognition_url":""})
        self.assertEqual(result["type"], "create_entry")


if __name__ == "__main__":
    unittest.main()
