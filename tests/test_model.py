"""Test that Fitssey data maps to physical calendar events."""

from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest

from fitssey.model import FitsseyDataError, parse_rooms, parse_schedule


def test_room_discovery_includes_rooms_without_classes() -> None:
    rooms = parse_rooms(
        {
            "collection": [
                {
                    "name": "Central",
                    "rooms": [
                        {"guid": "room-a", "qualifiedName": "Central - Room A"},
                        {"guid": "room-b", "name": "Room B"},
                    ],
                }
            ]
        }
    )
    assert [(room.guid, room.name) for room in rooms] == [
        ("room-a", "Central - Room A"),
        ("room-b", "Room B"),
    ]


def test_schedule_omits_cancelled_and_online_only_events() -> None:
    active = {
        "referenceId": "event-1",
        "qualifiedName": "Yoga",
        "startsAt": "2026-10-08T10:00:00+02:00",
        "endsAt": "2026-10-08T11:00:00+02:00",
        "room": {"guid": "room-a", "qualifiedName": "Central - Room A"},
        "isHidden": True,
    }
    payload = {
        "schedule": [
            {
                "date": "2026-10-08",
                "scheduleEvents": [
                    active,
                    {**active, "referenceId": "cancelled", "isCancelled": True},
                    {**active, "referenceId": "online", "room": None},
                    active,
                ],
            }
        ]
    }
    events = parse_schedule(payload, ZoneInfo("Europe/Warsaw"))
    assert len(events) == 1
    assert events[0].reference_id == "event-1"
    assert events[0].room_guid == "room-a"


def test_naive_timestamps_get_local_timezone_and_invalid_dates_are_skipped() -> None:
    payload = {
        "schedule": [
            {
                "scheduleEvents": [
                    {
                        "referenceId": "valid",
                        "startsAt": "2026-03-29T10:00:00",
                        "endsAt": "2026-03-29T11:00:00",
                        "room": {"guid": "room-a"},
                    },
                    {
                        "referenceId": "invalid",
                        "startsAt": "2026-03-29T12:00:00",
                        "endsAt": "2026-03-29T11:00:00",
                        "room": {"guid": "room-a"},
                    },
                ]
            }
        ]
    }
    events = parse_schedule(payload, ZoneInfo("Europe/Warsaw"))
    assert len(events) == 1
    assert events[0].starts_at.utcoffset() == timedelta(hours=2)


def test_bad_top_level_response_is_rejected() -> None:
    with pytest.raises(FitsseyDataError):
        parse_schedule([], ZoneInfo("Europe/Warsaw"))
