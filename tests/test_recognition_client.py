"""Exercise the real HA client with camera and network boundaries replaced."""
import asyncio
from datetime import datetime, timezone
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.wallpanel_photo_selector.recognition import setup_recognition

MODULE = "custom_components.wallpanel_photo_selector.recognition"


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tasks = []
        self.hass = MagicMock()
        self.hass.states.is_state.return_value = True
        self.entry = MagicMock()
        self.entry.entry_id = "test"
        self.entry.options = {
            "recognition_url": "http://worker:8099", "recognition_token": "x" * 32,
            "recognition_camera": "camera.portal", "recognition_person": "binary_sensor.portal",
        }
        def task(hass, coro, name):
            result = asyncio.create_task(coro)
            self.tasks.append(result)
            return result
        self.entry.async_create_background_task.side_effect = task
        self.data = {"photos": {"a.jpg": {}}}
        self.camera = AsyncMock(return_value=SimpleNamespace(content=b"jpeg", content_type="image/jpeg"))
        self.result = {"matches": [{"path":"a.jpg","people":2}], "viewer_count":2,
                       "next_expiry":datetime.now(timezone.utc).timestamp() + 900}
        async def chunks(size):
            raw = json.dumps(self.result).encode()
            yield raw[:8]
            yield raw[8:]
        self.response = MagicMock()
        self.response.content.iter_chunked = chunks
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=self.response)
        context.__aexit__ = AsyncMock(return_value=False)
        self.session = MagicMock()
        self.session.request.return_value = context
        self.stack = []
        for name, value in [
            ("async_get_image", self.camera),
            ("async_get_clientsession", MagicMock(return_value=self.session)),
            ("async_dispatcher_send", MagicMock()),
            ("async_track_time_interval", MagicMock()),
            ("async_track_state_change_event", MagicMock()),
        ]:
            patcher = patch(f"{MODULE}.{name}", value)
            patcher.start()
            self.stack.append(patcher)

    async def asyncTearDown(self):
        for task in self.tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        for patcher in self.stack:
            patcher.stop()

    async def start(self):
        setup_recognition(self.hass, self.entry, self.data)
        await asyncio.gather(*self.tasks)

    async def test_present_posts_camera_and_publishes_group_counts(self):
        await self.start()
        self.camera.assert_awaited_once()
        self.assertEqual(self.session.request.call_args.args, ("POST", "http://worker:8099/match"))
        self.assertEqual(self.data["viewer"]["status"], "matched")
        self.assertEqual(self.data["viewer"]["matches"][0]["people"], 2)

    async def test_absent_refreshes_memory_without_camera_capture(self):
        self.hass.states.is_state.return_value = False
        await self.start()
        self.camera.assert_not_awaited()
        self.assertEqual(self.session.request.call_args.args, ("GET", "http://worker:8099/matches"))
        self.assertEqual(self.data["viewer"]["status"], "matched")

    async def test_unknown_photos_never_published(self):
        self.result["matches"] = [{"path":"not-indexed.jpg","people":2}]
        await self.start()
        self.assertEqual(self.data["viewer"]["matches"], [])

    async def test_network_error_clears_matches(self):
        self.response.raise_for_status.side_effect = RuntimeError("Unavailable")
        await self.start()
        self.assertEqual(self.data["viewer"]["status"], "error")
        self.assertEqual(self.data["viewer"]["matches"], [])

    async def test_no_url_disables_recognition(self):
        self.entry.options = {}
        await self.start()
        self.assertEqual(self.data["viewer"]["status"], "disabled")
        self.session.request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
