"""Constants for the WallPanel Photo Selector integration."""

from homeassistant.const import Platform

DOMAIN = "wallpanel_photo_selector"
DEFAULT_MEDIA_PATH = "/media/PortalPhotos"
DEFAULT_SCAN_INTERVAL = 15
MIN_SCAN_INTERVAL = 1
MAX_SCAN_INTERVAL = 1440
PLATFORMS = [Platform.SENSOR, Platform.BUTTON]
