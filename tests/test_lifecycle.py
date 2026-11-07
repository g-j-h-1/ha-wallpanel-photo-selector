"""Options reload must release the old integration without recursive unloads."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.wallpanel_photo_selector import async_unload_entry
from custom_components.wallpanel_photo_selector.const import DOMAIN


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_unload_removes_panel_and_cancels_scan(self):
        hass, entry, task = MagicMock(), MagicMock(), MagicMock()
        entry.entry_id = "test"
        hass.data = {DOMAIN:{"test":{"scan_task":task}}}
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        with patch("custom_components.wallpanel_photo_selector.frontend.async_remove_panel") as remove:
            self.assertTrue(await async_unload_entry(hass, entry))
            remove.assert_called_once()
        entry.async_unload.assert_not_called()
        task.cancel.assert_called_once()
        self.assertNotIn(DOMAIN, hass.data)

    async def test_failed_platform_unload_keeps_runtime(self):
        hass, entry = MagicMock(), MagicMock()
        entry.entry_id = "test"
        data = {"scan_task":MagicMock()}
        hass.data = {DOMAIN:{"test":data}}
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
        self.assertFalse(await async_unload_entry(hass, entry))
        self.assertIs(hass.data[DOMAIN]["test"], data)
        data["scan_task"].cancel.assert_not_called()


if __name__ == "__main__":
    unittest.main()
