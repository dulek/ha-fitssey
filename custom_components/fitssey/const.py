"""Constants for the Fitssey integration."""

from datetime import timedelta

DOMAIN = "fitssey"
CONF_STUDIO_UUID = "studio_uuid"
CONF_API_KEY = "api_key"

POLL_INTERVAL = timedelta(minutes=5)
SCHEDULE_DAYS_AHEAD = 14
API_CACHE_SECONDS = 270
ROOM_CACHE_SECONDS = 3600
