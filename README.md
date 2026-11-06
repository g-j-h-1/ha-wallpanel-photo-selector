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
