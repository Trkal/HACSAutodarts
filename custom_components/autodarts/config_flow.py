"""Config flow for the Autodarts integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AutodartsAuthError, AutodartsCloudClient, AutodartsConnectionError
from .const import CONF_BOARD_ID, CONF_EMAIL, CONF_HOST, CONF_PASSWORD, CONF_PORT, DEFAULT_PORT, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class AutodartsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Autodarts."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._cloud_client: AutodartsCloudClient | None = None
        self._boards: dict[str, str] = {}
        self._user_input: dict[str, Any] = {}

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Step 1: Enter Autodarts email + password (and optional board host)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            cloud = AutodartsCloudClient(
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
                session,
            )
            try:
                await cloud.authenticate()
                boards = await cloud.get_boards()
            except AutodartsAuthError:
                errors["base"] = "invalid_auth"
            except AutodartsConnectionError:
                errors["base"] = "cannot_connect"
            else:
                self._cloud_client = cloud
                self._user_input = user_input
                self._boards = {
                    b["id"]: f"{b.get('name', b['id'])}" for b in boards
                }
                if not self._boards:
                    errors["base"] = "no_boards"
                elif len(self._boards) == 1:
                    # Only one board — skip selection step
                    board_id = next(iter(self._boards))
                    return self._create_entry(board_id)
                else:
                    return await self.async_step_board()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_board(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Step 2: Select which board to use."""
        if user_input is not None:
            return self._create_entry(user_input[CONF_BOARD_ID])

        board_schema = vol.Schema(
            {vol.Required(CONF_BOARD_ID): vol.In(self._boards)}
        )
        return self.async_show_form(
            step_id="board",
            data_schema=board_schema,
        )

    def _create_entry(self, board_id: str) -> ConfigFlowResult:
        """Create the config entry."""
        self._async_abort_entries_match({CONF_BOARD_ID: board_id})

        board_name = self._boards.get(board_id, board_id)
        data = {
            CONF_EMAIL: self._user_input[CONF_EMAIL],
            CONF_PASSWORD: self._user_input[CONF_PASSWORD],
            CONF_BOARD_ID: board_id,
        }
        # Optional local board connection
        if self._user_input.get(CONF_HOST):
            data[CONF_HOST] = self._user_input[CONF_HOST]
            data[CONF_PORT] = self._user_input.get(CONF_PORT, DEFAULT_PORT)

        return self.async_create_entry(
            title=f"Autodarts ({board_name})",
            data=data,
        )
