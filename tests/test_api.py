"""Test API authentication, pagination, and request caching."""

import asyncio
from datetime import date
from zoneinfo import ZoneInfo

import pytest

from fitssey.api import FitsseyApi, FitsseyAuthError


class FakeResponse:
    def __init__(self, status: int, payload: object) -> None:
        self.status = status
        self.payload = payload

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def json(self) -> object:
        return self.payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, str], dict[str, str]]] = []

    def get(self, url: str, *, params: dict[str, str], headers: dict[str, str], allow_redirects: bool, timeout: object) -> FakeResponse:
        assert allow_redirects is False
        self.calls.append((url, params, headers))
        return self.responses.pop(0)


def test_schedule_is_cached_and_key_only_appears_in_header() -> None:
    async def run() -> None:
        session = FakeSession([FakeResponse(200, {"schedule": []})])
        api = FitsseyApi(session, "studio-uuid", "secret-token", ZoneInfo("Europe/Warsaw"))
        first = await api.async_get_schedule(date(2026, 10, 8), date(2026, 10, 9))
        second = await api.async_get_schedule(date(2026, 10, 8), date(2026, 10, 9))
        assert first == second == ()
        assert len(session.calls) == 1
        url, params, headers = session.calls[0]
        assert "secret-token" not in url
        assert "secret-token" not in str(params)
        assert headers["Authorization"] == "Bearer secret-token"

    asyncio.run(run())


def test_rejected_key_does_not_appear_in_error() -> None:
    async def run() -> None:
        session = FakeSession([FakeResponse(403, {})])
        api = FitsseyApi(session, "studio-uuid", "secret-token", ZoneInfo("Europe/Warsaw"))
        with pytest.raises(FitsseyAuthError) as error:
            await api.async_get_schedule(date(2026, 10, 8), date(2026, 10, 8))
        assert "secret-token" not in str(error.value)

    asyncio.run(run())


def test_all_location_pages_are_read() -> None:
    async def run() -> None:
        session = FakeSession(
            [
                FakeResponse(200, {"pages": 2, "collection": [{"rooms": [{"guid": "a", "name": "A"}]}]}),
                FakeResponse(200, {"pages": 2, "collection": [{"rooms": [{"guid": "b", "name": "B"}]}]}),
            ]
        )
        api = FitsseyApi(session, "studio-uuid", "secret-token", ZoneInfo("Europe/Warsaw"))
        rooms = await api.async_get_rooms()
        assert {room.guid for room in rooms} == {"a", "b"}
        assert [call[1]["page"] for call in session.calls] == ["1", "2"]

    asyncio.run(run())
