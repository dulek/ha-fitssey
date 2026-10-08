"""UI setup and API-key rotation for Fitssey."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from zoneinfo import ZoneInfo

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import dt as dt_util

from .api import (
    FitsseyApi,
    FitsseyApiError,
    FitsseyAuthError,
    FitsseyStudioError,
    validate_studio_identifier,
)
from .const import CONF_API_KEY, CONF_STUDIO_ID, DOMAIN

STUDIO_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STUDIO_ID): TextSelector(),
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)
KEY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class FitsseyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure a Fitssey studio via the Home Assistant UI."""

    VERSION = 1

    async def _validate(
        self, studio_id: str, api_key: str
    ) -> dict[str, str]:
        """Check both endpoints needed by this integration."""
        api = FitsseyApi(
            async_get_clientsession(self.hass),
            studio_id,
            api_key,
            ZoneInfo(self.hass.config.time_zone),
        )
        try:
            await api.async_get_rooms()
            # Room access alone does not prove access to the schedule.
            today = dt_util.now().date()
            await api.async_get_schedule(today, today)
        except FitsseyAuthError:
            return {"base": "invalid_auth"}
        except FitsseyStudioError:
            return {"base": "invalid_studio"}
        except FitsseyApiError:
            return {"base": "cannot_connect"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a studio entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                studio_id = validate_studio_identifier(user_input[CONF_STUDIO_ID])
            except ValueError:
                errors[CONF_STUDIO_ID] = "invalid_identifier"
            else:
                await self.async_set_unique_id(studio_id.casefold())
                self._abort_if_unique_id_configured()
                if not (errors := await self._validate(studio_id, user_input[CONF_API_KEY])):
                    return self.async_create_entry(
                        title=f"Fitssey {studio_id}",
                        data={
                            CONF_STUDIO_ID: studio_id,
                            CONF_API_KEY: user_input[CONF_API_KEY],
                        },
                    )
        return self.async_show_form(
            step_id="user", data_schema=STUDIO_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Prompt for a replacement API key after authentication fails."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and store a replacement key."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._validate(
                entry.data[CONF_STUDIO_ID],
                user_input[CONF_API_KEY],
            )
            if not errors:
                await self.async_set_unique_id(entry.unique_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=KEY_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow proactive API-key rotation."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._validate(
                entry.data[CONF_STUDIO_ID],
                user_input[CONF_API_KEY],
            )
            if not errors:
                await self.async_set_unique_id(entry.unique_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                )
        return self.async_show_form(
            step_id="reconfigure", data_schema=KEY_SCHEMA, errors=errors
        )
