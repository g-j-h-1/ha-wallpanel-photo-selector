# Anonymous viewer recognition — installation and commissioning

This is an optional companion service for the Home Assistant integration and
the matching `lovelace-wallpanel-photo-selector` frontend changes. Installing
only this service will not change your slideshow. It requires no people tags.

The worker indexes faces in the resized exported JPEGs, without changing them.
Your Nikon NEF originals, JPEG originals, ratings, Lightroom catalogue and any
Lightroom people tags remain managed in Lightroom. Face signatures are a separate,
rebuildable index, not Lightroom metadata. Small faces in resized exports may not
match reliably; increase export resolution if necessary.

## How selection works

- Home Assistant captures a camera frame every five seconds only while the
  person sensor is on. While it is off, HA refreshes remembered matches without
  accessing the camera.
- A coarse frontal-face check estimates facing direction, not eye gaze. A face
  must match across two successive frames before it enters visitor memory.
- Anonymous visitors remain in memory for 15 minutes after their last confirmed
  sighting. Recognising them again restarts their timer. Memory is kept in RAM
  and resets when the service restarts. Camera frames are not saved.
- Each next photo is selected from the full eligible library using its normal
  rating weight multiplied by `1 + 9 × n²`, where `n` is the number of remembered
  visitors matched in that photo. The multipliers are 1, 10, 37, 82 for 0–3 people.
  This favours group photos but does not guarantee them. Zero-weight ratings
  remain excluded. Filename filters still apply.
- With the viewer entity configured, the configured photo history is honoured
  without the usual 25% small-library cap. Matching photos in history receive
  no exception. If every eligible photo is in history, the oldest exclusions
  are released until a different photo can display. An immediate repeat is
  avoided whenever at least two eligible photos exist. With only one eligible
  photo, there is no distinct image to display.
- Photo history counts selections and is local to the dashboard session. The
  separate 15-minute timer concerns people, not photographs. Reloading the
  dashboard resets selection history.
- Worker errors, missing faces and expired matches restore the normal rating
  weights. Viewer information expires after at most 15 seconds without a refresh.

## 1. Prepare the recognition VM

For the i7-7820HQ / 16 GB host, start with an Ubuntu Server VM with 2 virtual CPUs,
3 GB RAM and 20 GB disk, on bridged networking. Check the HA VM's existing RAM
allocation first. The reported Windows drive had approximately 7 GB free:
free sufficient space or put the new VM on another drive before creating it.
CPU recognition is sufficient to start; no GPU passthrough is required. Actual
indexing and matching latency depends on the library and must be measured locally.

Install Docker Engine and its Compose plugin using Docker's Ubuntu instructions:
https://docs.docker.com/engine/install/ubuntu/

The recognition VM must have read access to **the same exported JPEG folder**
that HA indexes, with the same relative subfolder paths. One option for HA OS is
to enable its Samba share app, mount its `media` share read-only in Ubuntu, and
use `/srv/ha-media/PortalPhotos`. Give container UID 10001 read/traverse access.
Use a credentials file for the SMB mount; do not put passwords in command lines
or source control. Mount the share before starting the service and make that
mount persistent across reboots. Do not use the Windows path or a directory of
NEF originals as the worker's photo directory.

## 2. Start the service

Copy this `recognition` directory to the VM. In that directory, generate a token:

```sh
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

Create a local `.env` file containing the result and your mounted export path:

```dotenv
RECOGNITION_TOKEN=replace_with_the_generated_token
PHOTO_EXPORT_DIRECTORY=/srv/ha-media/PortalPhotos
```

Then run:

```sh
docker compose up -d --build
docker compose logs -f
```

The initial build compiles dlib and can take several minutes. Initial indexing
also takes time. The worker checks for changed, new and removed JPEGs every
minute. Unchanged images reuse SQLite embeddings in the `face-index` volume.
The HA metadata scanner retains its separately configured scan interval.

The worker accepts a bearer token on `/health`, `/match` and `/matches`.
`/health` reports `state`, indexed photo/face counts and indexing error count.
From the VM, check it without placing the token itself in shell history:

```sh
read -rsp 'Recognition token: ' recognition_token; echo
curl --fail -H "Authorization: Bearer $recognition_token" http://localhost:8099/health
unset recognition_token
```

The sample Compose file exposes port 8099 to the LAN. Restrict access to the HA
VM using your network firewall and do not forward this port from the internet.
HTTP is suitable only on your trusted local network; use an HTTPS reverse proxy
if the connection crosses an untrusted network. The dashboard itself need not
use HTTPS because HA obtains the camera images through the ESPHome integration.

## 3. Configure Home Assistant

Back up the existing custom component. Install the updated
`custom_components/wallpanel_photo_selector` directory and restart HA. Keep the
existing integration entry and its media folder configuration.

Open **Settings → Devices & services → WallPanel Photo Selector → Configure**:

| Setting | Value for your Portal |
|---|---|
| Recognition service URL | `http://RECOGNITION_VM_IP:8099` |
| Recognition service token | Same token as the worker's `.env` |
| Viewer camera | `camera.garage_facebook_portalmini_camera` |
| Person detected sensor | `binary_sensor.garage_facebook_portalmini_person` |

The URL is an origin only, without `/match` or any other path. The token is the
worker token, not a Home Assistant long-lived token. No HA token is given to the
worker. The backend calls HA's camera API internally.

Find the new **Viewer match** sensor on the integration's device. Its state is
`matched`, `no_match`, `waiting`, `idle`, `error` or `disabled`; its attributes
contain relative photo paths with visitor counts, a visitor total and an expiry.
`error` includes authentication and connection errors; check the worker's health
and HA logs. Clearing the recognition URL disables the optional feature.

## 4. Configure the dashboard

Install the updated frontend `wallpanel.js` from the companion repository, then
reload the Portal dashboard (and clear the frontend cache if necessary).
Add these settings to the existing `wallpanel:` block, retaining your other options:

```yaml
photo_selector_enabled: true
media_order: random
photo_selector_history_size: 50
photo_selector_viewer_entity: sensor.wallpanel_photo_selector_viewer_match
```

Verify the sensor's actual entity ID in your installation; HA may append a suffix
if a name is already taken. The sample history of 50 refers to the previous 50
selections. Keep your existing `image_url` and rating frequency settings.

## 5. Check behaviour before leaving it unattended

1. Confirm `/health` is `ready` with a nonzero face count and HA's scan has finished.
2. With nobody present, check that rating-weighted selection continues.
3. Face the Portal for 10–15 seconds. The sensor should show remembered visitors
   and matched relative paths. Verify those paths really contain the viewer.
4. Repeat with another person, then check group-photo visitor counts.
5. Leave the camera view: visitor counts should remain until the rolling
   15-minute timers expire. Restarting the worker clears these timers immediately.
6. Stop the worker: the slideshow should keep advancing using normal rating weights.
7. Check a small group-photo subset: those photos should remain excluded while
   in history, with other library photos filling the gaps.

Distance 0.45 is a conservative starting threshold, not a confidence percentage.
Lighting, pose, lookalikes and low-resolution faces can cause misses or false
matches. Lower `FACE_DISTANCE_THRESHOLD` in Compose for stricter matching and
recreate the container. Test with your household before adjusting it upward.

The worker currently shortlists at most 200 matched photo paths per refresh,
ordered by visitor count and path; all other photos remain eligible at normal
weight. A very large library may benefit from a larger, paginated match API in
a future version. Matching is for one Portal camera per worker instance.

## Rollback

Remove `photo_selector_viewer_entity` from the dashboard and clear the backend
recognition URL to restore the previous selection behaviour. Stop the worker
with `docker compose down`. Its photo index remains in the named volume; removing
that volume explicitly deletes the rebuildable face signatures, never originals.
