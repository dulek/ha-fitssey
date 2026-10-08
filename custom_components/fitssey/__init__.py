"""Read-only Fitssey integration for Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FitsseyApi
from .const import CONF_API_KEY, CONF_STUDIO_UUID
from .coordinator import FitsseyCoordinator

PLATFORMS = [Platform.CALENDAR]


@dataclass(slots=True)
class FitsseyRuntime:
    """Objects shared by the Fitssey platforms."""

    api: FitsseyApi
    coordinator: FitsseyCoordinator


type FitsseyConfigEntry = ConfigEntry[FitsseyRuntime]


async def async_setup_entry(hass: HomeAssistant, entry: FitsseyConfigEntry) -> bool:
    """Set up a Fitssey studio."""
    api = FitsseyApi(
        async_get_clientsession(hass),
        entry.data[CONF_STUDIO_UUID],
        entry.data[CONF_API_KEY],
        ZoneInfo(hass.config.time_zone),
    )
    coordinator = FitsseyCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = FitsseyRuntime(api, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FitsseyConfigEntry) -> bool:
    """Unload a Fitssey studio."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
