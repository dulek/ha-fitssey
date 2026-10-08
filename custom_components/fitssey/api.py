"""Small read-only client for Fitssey API v4."""

from __future__ import annotations

import asyncio
from datetime import date
import json
from typing import Any
from zoneinfo import ZoneInfo

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import API_CACHE_SECONDS, ROOM_CACHE_SECONDS
from .model import FitsseyDataError, FitsseyEvent, FitsseyRoom, parse_rooms, parse_schedule


class FitsseyApiError(Exception):
    """A Fitssey request could not be completed."""


class FitsseyAuthError(FitsseyApiError):
    """The API key was rejected."""


class FitsseyStudioError(FitsseyApiError):
    """The studio UUID was not found."""


class FitsseyApi:
    """Fetch room and schedule data without exposing credentials in errors."""

    def __init__(
        self,
        session: ClientSession,
        studio_uuid: str,
        api_key: str,
        local_timezone: ZoneInfo,
    ) -> None:
        self._session = session
        self._base_url = f"https://app.fitssey.com/{studio_uuid}/api/v4/public"
        self._api_key = api_key
        self._timezone = local_timezone
        self._lock = asyncio.Lock()
        self._schedule_cache: dict[
            tuple[date, date], tuple[float, tuple[FitsseyEvent, ...]]
        ] = {}
        self._rooms_cache: tuple[float, tuple[FitsseyRoom, ...]] | None = None

    async def _get_json(self, path: str, params: dict[str, str]) -> Any:
        try:
            async with self._session.get(
                f"{self._base_url}{path}",
                params=params,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
                allow_redirects=False,
                timeout=ClientTimeout(total=20),
            ) as response:
                if response.status in (401, 403):
                    raise FitsseyAuthError("API key rejected")
                if response.status == 404:
                    raise FitsseyStudioError("Studio not found")
                if response.status != 200:
                    raise FitsseyApiError(f"HTTP {response.status}")
                return await response.json()
        except (ClientError, asyncio.TimeoutError, json.JSONDecodeError) as err:
            raise FitsseyApiError("Unable to read Fitssey response") from err

    async def async_get_rooms(self) -> tuple[FitsseyRoom, ...]:
        """Get all rooms, including those without upcoming classes."""
        now = asyncio.get_running_loop().time()
        if self._rooms_cache and now - self._rooms_cache[0] < ROOM_CACHE_SECONDS:
            return self._rooms_cache[1]

        async with self._lock:
            now = asyncio.get_running_loop().time()
            if self._rooms_cache and now - self._rooms_cache[0] < ROOM_CACHE_SECONDS:
                return self._rooms_cache[1]

            rooms: dict[str, FitsseyRoom] = {}
            page = 1
            while True:
                payload = await self._get_json(
                    "/location/all", {"page": str(page), "count": "1000"}
                )
                try:
                    parsed = parse_rooms(payload)
                except FitsseyDataError as err:
                    raise FitsseyApiError("Invalid locations response") from err
                rooms.update((room.guid, room) for room in parsed)

                pages = payload.get("pages")
                if isinstance(pages, int) and not isinstance(pages, bool):
                    if page >= pages:
                        break
                elif len(payload["collection"]) < 1000:
                    break
                page += 1
                if page > 100:
                    raise FitsseyApiError("Too many locations pages")

            result = tuple(rooms.values())
            self._rooms_cache = (asyncio.get_running_loop().time(), result)
            return result

    async def async_get_schedule(
        self, start_date: date, end_date: date
    ) -> tuple[FitsseyEvent, ...]:
        """Get individual classes for an inclusive date range."""
        if end_date < start_date:
            return ()
        key = (start_date, end_date)
        now = asyncio.get_running_loop().time()
        cached = self._schedule_cache.get(key)
        if cached and now - cached[0] < API_CACHE_SECONDS:
            return cached[1]

        async with self._lock:
            now = asyncio.get_running_loop().time()
            cached = self._schedule_cache.get(key)
            if cached and now - cached[0] < API_CACHE_SECONDS:
                return cached[1]
            payload = await self._get_json(
                "/schedule",
                {
                    "startDate": start_date.isoformat(),
                    "endDate": end_date.isoformat(),
                },
            )
            try:
                events = parse_schedule(payload, self._timezone)
            except FitsseyDataError as err:
                raise FitsseyApiError("Invalid schedule response") from err
            if len(self._schedule_cache) >= 16:
                oldest = min(self._schedule_cache, key=lambda item: self._schedule_cache[item][0])
                del self._schedule_cache[oldest]
            self._schedule_cache[key] = (asyncio.get_running_loop().time(), events)
            return events
