# WallPanel Photo Selector — Home Assistant integration

Backend companion to [Lovelace WallPanel Photo Selector](https://github.com/g-j-h-1/lovelace-wallpanel-photo-selector). Scans local JPEGs under `/media`, reads star ratings and orientation, and exposes an indexed photo list to the WallPanel frontend.

## Install and update with HACS

1. In HACS, open **Custom repositories** and add `https://github.com/g-j-h-1/ha-wallpanel-photo-selector` as type **Integration**.
2. Find **WallPanel Photo Selector**, download it, and restart Home Assistant.
3. If this integration was already installed manually, **do not delete the existing integration or its configuration entry**. Installing via HACS should replace the same `custom_components/wallpanel_photo_selector` code directory. Restart Home Assistant after installation.

## Configure

Go to **Settings → Devices & services → Add integration → WallPanel Photo Selector** if not previously configured. The default folder is `/media/PortalPhotos`, with an automatic scan every 15 minutes. Existing users should retain their configured path and interval.

## Scan diagnostics and manual rescan

The integration indexes photos on startup and periodically thereafter. The **WallPanel Photo Selector** device provides scan status, last scan time, ratings and orientation counts. Press **Rescan photos** on the device to request an immediate rescan. Manual and scheduled scans cannot overlap.

## Compatibility

The frontend is installed separately through HACS as a Dashboard component from the original repository. This repository contains only the Home Assistant backend integration.

## Browse photographs by rating and errors

After restarting Home Assistant, open **Photo Library** in the sidebar. The read-only browser lists indexed JPEG filenames and their star ratings, with filters for **All**, **0–5 stars**, and **Errors**. Use the search box to find filenames or error messages. The Errors tab also lists unreadable JPEGs that could not be added to the index.

The **Refresh list** button reloads the current index; to rescan the underlying directory, use the integration's **Rescan photos** button.

## Optional Immich person-aware slideshow (1.1.6)

To prioritise photos of people recognised by your kiosk, copy an Immich name index to `/media/PortalPhotos/immich-people.json` (or to the configured media directory). The JSON must map photo filenames **relative to that directory**, using forward slashes, to arrays of person names:

```json
{
  "Holiday/IMG_0001.jpg": ["Person A"],
  "IMG_0002.jpg": ["Person A", "Person B"]
}
```

The index is optional; missing, malformed, or unmatched entries are ignored and the normal slideshow continues. The authenticated `wallpanel_photo_selector/photos` WebSocket response now includes `people` on each photo and `people_indexed` for diagnostics. The index is re-read whenever a kiosk requests the photo list. You must also enable `photo_selector_person_entity: input_text.portal_recognised_people` in the kiosk's `wallpanel:` configuration and install the corresponding updated kiosk release.

**Important:** Photo names in the JSON must match the indexed filenames exactly, including directory prefixes and case. Keep this private mapping file in Home Assistant's media directory, not in a public GitHub repository.
