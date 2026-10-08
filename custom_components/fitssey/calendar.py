"""One read-only calendar for each Fitssey room."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import FitsseyConfigEntry
from .coordinator import FitsseyCoordinator
from .model import FitsseyEvent


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FitsseyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up calendars and discover rooms added later."""
    coordinator = entry.runtime_data.coordinator
    known_rooms: set[str] = set()

    @callback
    def add_new_rooms() -> None:
        new_rooms = coordinator.data.rooms.keys() - known_rooms
        if new_rooms:
            async_add_entities(
                FitsseyRoomCalendar(coordinator, entry, room_guid)
                for room_guid in sorted(new_rooms)
            )
            known_rooms.update(new_rooms)

    add_new_rooms()
    entry.async_on_unload(coordinator.async_add_listener(add_new_rooms))


class FitsseyRoomCalendar(CoordinatorEntity[FitsseyCoordinator], CalendarEntity):
    """A room's scheduled classes."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: FitsseyCoordinator,
        entry: FitsseyConfigEntry,
        room_guid: str,
    ) -> None:
        super().__init__(coordinator)
        self._room_guid = room_guid
        self._attr_unique_id = f"{entry.unique_id}_{room_guid}"

    @property
    def name(self) -> str:
        """Return the current room name."""
        room = self.coordinator.data.rooms.get(self._room_guid)
        return f"Fitssey {room.name if room else self._room_guid}"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the active or next scheduled class."""
        now = dt_util.now()
        for event in self.coordinator.data.events:
            if event.room_guid == self._room_guid and event.ends_at > now:
                return self._as_calendar_event(event)
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return all classes overlapping the requested interval."""
        events = await self.coordinator.async_events_in_range(start_date, end_date)
        return [
            self._as_calendar_event(event)
            for event in events
            if event.room_guid == self._room_guid
        ]

    def _as_calendar_event(self, event: FitsseyEvent) -> CalendarEvent:
        return CalendarEvent(
            summary=event.name,
            start=dt_util.as_local(event.starts_at),
            end=dt_util.as_local(event.ends_at),
            location=event.room_name,
            uid=event.reference_id,
        )
