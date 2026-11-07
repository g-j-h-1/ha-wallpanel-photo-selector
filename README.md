# WallPanel Photo Selector — Home Assistant integration

Backend companion to [Lovelace WallPanel Photo Selector](https://github.com/g-j-h-1/lovelace-wallpanel-photo-selector). Scans local JPEGs under `/media`, reads star ratings and orientation, and exposes an indexed photo list to the WallPanel frontend.

## Optional anonymous viewer recognition

An optional local worker can match the Portal camera's faces against exported
JPEGs without names or manual tagging. It remembers visitors for 15 minutes and
boosts photo selection weights for photos containing them, with larger boosts
for group photos. The full library remains available and the slideshow keeps
advancing. Requires the matching frontend update and a separate recognition
service. See [installation and behaviour](recognition/README.md).

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
