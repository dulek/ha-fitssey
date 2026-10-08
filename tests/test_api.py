"""Test API authentication, pagination, and request caching."""

import asyncio
from datetime import date
from zoneinfo import ZoneInfo

import pytest

from fitssey.api import FitsseyApi, FitsseyAuthError, validate_studio_identifier


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
        api = FitsseyApi(session, "example-studio", "secret-token", ZoneInfo("Europe/Warsaw"))
        first = await api.async_get_schedule(date(2026, 10, 8), date(2026, 10, 9))
        second = await api.async_get_schedule(date(2026, 10, 8), date(2026, 10, 9))
        assert first == second == ()
        assert len(session.calls) == 1
        url, params, headers = session.calls[0]
        assert url == "https://app.fitssey.com/example-studio/api/v4/public/schedule"
        assert "secret-token" not in url
        assert "secret-token" not in str(params)
        assert headers["Authorization"] == "Bearer secret-token"

    asyncio.run(run())


@pytest.mark.parametrize(
    "identifier",
    ["example-studio", "Studio Name 2", "studio.example", "ćwiczenia"],
)
def test_studio_identifier_accepts_nonempty_text(identifier: str) -> None:
    assert validate_studio_identifier(f" {identifier} ") == identifier


@pytest.mark.parametrize("identifier", ["", "   ", ".", "..", "studio\nname", "x" * 256])
def test_studio_identifier_rejects_blank_or_control_values(identifier: str) -> None:
    with pytest.raises(ValueError):
        validate_studio_identifier(identifier)


def test_identifier_is_encoded_as_one_url_segment() -> None:
    async def run() -> None:
        session = FakeSession([FakeResponse(200, {"schedule": []})])
        api = FitsseyApi(session, "Studio Name/2", "secret-token", ZoneInfo("Europe/Warsaw"))
        await api.async_get_schedule(date(2026, 10, 8), date(2026, 10, 8))
        assert session.calls[0][0] == (
            "https://app.fitssey.com/Studio%20Name%2F2/api/v4/public/schedule"
        )

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
