"""Data models and parsing for the Fitssey API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


class FitsseyDataError(Exception):
    """The API returned data with an unexpected shape."""


@dataclass(frozen=True, slots=True)
class FitsseyRoom:
    """A studio room."""

    guid: str
    name: str


@dataclass(frozen=True, slots=True)
class FitsseyEvent:
    """An individual scheduled class."""

    reference_id: str
    name: str
    starts_at: datetime
    ends_at: datetime
    room_guid: str
    room_name: str


def parse_rooms(payload: Any) -> tuple[FitsseyRoom, ...]:
    """Extract rooms from a /location/all page."""
    if not isinstance(payload, dict) or not isinstance(payload.get("collection"), list):
        raise FitsseyDataError("Invalid locations response")

    result: dict[str, FitsseyRoom] = {}
    for location in payload["collection"]:
        if not isinstance(location, dict) or not isinstance(location.get("rooms"), list):
            continue
        location_name = location.get("name")
        for room in location["rooms"]:
            if not isinstance(room, dict):
                continue
            guid = room.get("guid")
            if not isinstance(guid, str) or not guid:
                continue
            name = room.get("qualifiedName") or room.get("name")
            if not isinstance(name, str) or not name:
                name = f"{location_name} - {guid}" if location_name else guid
            result[guid] = FitsseyRoom(guid, name)
    return tuple(result.values())


def parse_schedule(payload: Any, local_timezone: ZoneInfo) -> tuple[FitsseyEvent, ...]:
    """Extract physical, non-cancelled classes from /schedule."""
    if not isinstance(payload, dict) or not isinstance(payload.get("schedule"), list):
        raise FitsseyDataError("Invalid schedule response")

    result: dict[str, FitsseyEvent] = {}
    for day in payload["schedule"]:
        if not isinstance(day, dict) or not isinstance(day.get("scheduleEvents"), list):
            continue
        for item in day["scheduleEvents"]:
            if not isinstance(item, dict) or item.get("isCancelled") is True:
                continue
            room = item.get("room")
            if not isinstance(room, dict):
                continue
            reference_id = item.get("referenceId")
            room_guid = room.get("guid")
            start_text = item.get("startsAt")
            end_text = item.get("endsAt")
            if not all(
                isinstance(value, str) and value
                for value in (reference_id, room_guid, start_text, end_text)
            ):
                continue
            try:
                starts_at = datetime.fromisoformat(start_text)
                ends_at = datetime.fromisoformat(end_text)
            except ValueError:
                continue
            if starts_at.tzinfo is None:
                starts_at = starts_at.replace(tzinfo=local_timezone)
            if ends_at.tzinfo is None:
                ends_at = ends_at.replace(tzinfo=local_timezone)
            if ends_at <= starts_at:
                continue
            name = item.get("qualifiedName")
            room_name = room.get("qualifiedName")
            result[reference_id] = FitsseyEvent(
                reference_id=reference_id,
                name=name if isinstance(name, str) and name else "Fitssey class",
                starts_at=starts_at,
                ends_at=ends_at,
                room_guid=room_guid,
                room_name=(
                    room_name
                    if isinstance(room_name, str) and room_name
                    else room_guid
                ),
            )
    return tuple(sorted(result.values(), key=lambda event: (event.starts_at, event.reference_id)))
