"""Optional camera recognition client; failures never stop the photo scanner."""
import asyncio
from datetime import datetime, timedelta, timezone
import logging

import aiohttp
from homeassistant.components.camera import async_get_image
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)


def setup_recognition(hass, entry, data):
    """Poll only while presence is on; discard results if presence changes."""
    options = entry.options
    base_url = options.get("recognition_url", "").rstrip("/")
    token = options.get("recognition_token", "")
    camera = options.get("recognition_camera", "")
    person = options.get("recognition_person", "")
    data["viewer"] = {"status": "disabled", "matches": [], "expires_at": None}
    if not all((base_url, token, camera, person)):
        return
    generation = 0
    pending = None

    def publish(status, matches=None, viewer_count=0, next_expiry=None):
        expires = datetime.now(timezone.utc) + timedelta(seconds=15)
        if next_expiry is not None:
            expires = min(expires, datetime.fromtimestamp(float(next_expiry), timezone.utc))
        data["viewer"] = {
            "status": status, "matches": matches or [], "viewer_count": viewer_count,
            "expires_at": expires.isoformat() if matches else None,
        }
        async_dispatcher_send(hass, f"{DOMAIN}_updated_{entry.entry_id}")

    def present():
        return hass.states.is_state(person, "on")

    async def capture(epoch):
        try:
            headers = {"Authorization": f"Bearer {token}"}
            if present():
                image = await async_get_image(hass, camera, timeout=10)
                headers["Content-Type"] = image.content_type
                method, endpoint, body = "POST", "/match", image.content
            else:
                method, endpoint, body = "GET", "/matches", None
            async with async_get_clientsession(hass).request(
                method, f"{base_url}{endpoint}", data=body, headers=headers,
                timeout=aiohttp.ClientTimeout(total=10), allow_redirects=False,
            ) as response:
                response.raise_for_status()
                # Do not follow redirects or accept unbounded worker responses.
                raw = bytearray()
                async for chunk in response.content.iter_chunked(8192):
                    raw.extend(chunk)
                    if len(raw) > 65536:
                        raise ValueError("Recognition response too large")
                import json
                result = json.loads(raw)
            if epoch != generation:
                return
            matches = result.get("matches", [])
            if not isinstance(matches, list) or len(matches) > 200 or any(
                not isinstance(m, dict) or not isinstance(m.get("path"), str)
                or type(m.get("people")) is not int or not 1 <= m["people"] <= 100
                for m in matches
            ):
                raise ValueError("Invalid recognition result")
            matches = [m for m in matches if m["path"] in data["photos"]]
            publish("matched" if matches else "no_match", matches, result.get("viewer_count", 0), result.get("next_expiry"))
        except asyncio.CancelledError:
            raise
        except Exception:
            if epoch == generation:
                previous_status = data["viewer"]["status"]
                publish("error")
                if previous_status != "error":
                    LOGGER.warning("Viewer recognition unavailable; using normal photo selection")

    @callback
    def tick(_now=None):
        nonlocal pending
        if pending is None or pending.done():
            pending = entry.async_create_background_task(hass, capture(generation), "WallPanel viewer recognition")

    async def presence_changed(event):
        nonlocal generation
        old, new = event.data.get("old_state"), event.data.get("new_state")
        if old and new and old.state == new.state:
            return
        generation += 1
        # Keep the previous visitor memory while presence changes. Its freshness
        # TTL expires automatically if the next request fails or never completes.
        if pending and not pending.done():
            pending.cancel()
        # The interval captures after a new presence state, allowing cancellation to settle.

    entry.async_on_unload(async_track_state_change_event(hass, [person], presence_changed))
    entry.async_on_unload(async_track_time_interval(hass, tick, timedelta(seconds=5)))
    publish("waiting" if present() else "idle")
    tick()
