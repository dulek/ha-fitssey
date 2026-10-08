"""Coordinate Fitssey schedule updates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import FitsseyApi, FitsseyApiError, FitsseyAuthError
from .const import DOMAIN, POLL_INTERVAL, SCHEDULE_DAYS_AHEAD
from .model import FitsseyEvent, FitsseyRoom

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FitsseySnapshot:
    """Near-term schedule used by calendar states and automations."""

    start_date: date
    end_date: date
    rooms: dict[str, FitsseyRoom]
    events: tuple[FitsseyEvent, ...]


class FitsseyCoordinator(DataUpdateCoordinator[FitsseySnapshot]):
    """Keep a near-term schedule fresh without polling per room."""

    def __init__(self, hass: HomeAssistant, api: FitsseyApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=POLL_INTERVAL,
            always_update=True,
        )
        self.api = api

    async def _async_update_data(self) -> FitsseySnapshot:
        today = dt_util.now().date()
        start_date = today - timedelta(days=1)
        end_date = today + timedelta(days=SCHEDULE_DAYS_AHEAD)
        try:
            rooms = {room.guid: room for room in await self.api.async_get_rooms()}
            events = await self.api.async_get_schedule(start_date, end_date)
        except FitsseyAuthError as err:
            raise ConfigEntryAuthFailed("Fitssey API key rejected") from err
        except FitsseyApiError as err:
            raise UpdateFailed("Unable to update Fitssey schedule") from err

        # A class can refer to a room absent from /location/all. Keep it visible.
        for event in events:
            rooms.setdefault(event.room_guid, FitsseyRoom(event.room_guid, event.room_name))
        return FitsseySnapshot(start_date, end_date, rooms, events)

    async def async_events_in_range(
        self, start_date: datetime, end_date: datetime
    ) -> tuple[FitsseyEvent, ...]:
        """Return events from the near-term snapshot or a cached API request."""
        api_start = start_date.date() - timedelta(days=1)
        api_end = end_date.date() + timedelta(days=1)
        snapshot = self.data
        if snapshot and snapshot.start_date <= api_start and api_end <= snapshot.end_date:
            events = snapshot.events
        else:
            try:
                events = await self.api.async_get_schedule(api_start, api_end)
            except FitsseyApiError as err:
                raise HomeAssistantError("Unable to read Fitssey schedule") from err
        return tuple(
            event
            for event in events
            if event.ends_at > start_date and event.starts_at < end_date
        )
