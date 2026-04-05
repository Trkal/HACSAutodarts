"""Config flow for the Autodarts integration."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AutodartsApiClient
from .const import CONF_HOST, CONF_PORT, DEFAULT_PORT, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class AutodartsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Autodarts."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            # Abort if this board is already configured
            self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})

            session = async_get_clientsession(self.hass)
            client = AutodartsApiClient(host, port, session)

            if await client.test_connection():
                return self.async_create_entry(
                    title=f"Autodarts ({host})",
                    data=user_input,
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
