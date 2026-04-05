"""Config flow for the Autodarts integration."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import parse_qs, urlparse

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    AutodartsAuthError,
    AutodartsCloudClient,
    AutodartsConnectionError,
    build_authorize_url,
    exchange_code,
    generate_pkce,
)
from .const import CONF_BOARD_ID, CONF_HOST, CONF_PORT, CONF_TOKEN, DEFAULT_PORT, DOMAIN


class AutodartsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Autodarts."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._code_verifier: str | None = None
        self._token: dict[str, Any] = {}
        self._boards: dict[str, str] = {}
        self._user_input: dict[str, Any] = {}

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Step 1: Optional local board IP, then redirect to auth step."""
        if user_input is not None:
            self._user_input = user_input
            return await self.async_step_auth()

        schema = vol.Schema(
            {
                vol.Optional(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_auth(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Step 2: User logs in via browser and pastes the redirect URL."""
        errors: dict[str, str] = {}

        if user_input is None:
            # Generate PKCE pair and build authorize URL
            self._code_verifier, challenge = generate_pkce()
            auth_url = build_authorize_url(challenge)
            return self.async_show_form(
                step_id="auth",
                data_schema=vol.Schema({vol.Required("redirect_url"): str}),
                description_placeholders={"authorize_url": auth_url},
            )

        # User pasted the redirect URL — extract the code
        redirect_url = user_input["redirect_url"].strip()
        parsed = urlparse(redirect_url)
        qs = parse_qs(parsed.query)
        code = qs.get("code", [None])[0]

        if not code:
            errors["redirect_url"] = "no_code"
            # Regenerate auth URL
            self._code_verifier, challenge = generate_pkce()
            auth_url = build_authorize_url(challenge)
            return self.async_show_form(
                step_id="auth",
                data_schema=vol.Schema({vol.Required("redirect_url"): str}),
                description_placeholders={"authorize_url": auth_url},
                errors=errors,
            )

        # Exchange the code for tokens
        session = async_get_clientsession(self.hass)
        try:
            token_data = await exchange_code(session, code, self._code_verifier)  # type: ignore[arg-type]
        except AutodartsAuthError:
            errors["redirect_url"] = "invalid_code"
            self._code_verifier, challenge = generate_pkce()
            auth_url = build_authorize_url(challenge)
            return self.async_show_form(
                step_id="auth",
                data_schema=vol.Schema({vol.Required("redirect_url"): str}),
                description_placeholders={"authorize_url": auth_url},
                errors=errors,
            )
        except AutodartsConnectionError:
            errors["base"] = "cannot_connect"
            self._code_verifier, challenge = generate_pkce()
            auth_url = build_authorize_url(challenge)
            return self.async_show_form(
                step_id="auth",
                data_schema=vol.Schema({vol.Required("redirect_url"): str}),
                description_placeholders={"authorize_url": auth_url},
                errors=errors,
            )

        # Normalise token for storage
        self._token = {
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token"),
            "expires_at": time.time() + token_data.get("expires_in", 300),
        }

        # Fetch boards
        cloud = AutodartsCloudClient(session, self._token)
        try:
            boards = await cloud.get_boards()
        except AutodartsConnectionError:
            errors["base"] = "cannot_connect"
            self._code_verifier, challenge = generate_pkce()
            auth_url = build_authorize_url(challenge)
            return self.async_show_form(
                step_id="auth",
                data_schema=vol.Schema({vol.Required("redirect_url"): str}),
                description_placeholders={"authorize_url": auth_url},
                errors=errors,
            )

        self._boards = {b["id"]: b.get("name", b["id"]) for b in boards}

        if not self._boards:
            return self.async_abort(reason="no_boards")
        if len(self._boards) == 1:
            return self._create_entry(next(iter(self._boards)))
        return await self.async_step_board()

    async def async_step_board(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Step 3: Select which board to use."""
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
        data: dict[str, Any] = {
            CONF_TOKEN: self._token,
            CONF_BOARD_ID: board_id,
        }
        if self._user_input.get(CONF_HOST):
            data[CONF_HOST] = self._user_input[CONF_HOST]
            data[CONF_PORT] = self._user_input.get(CONF_PORT, DEFAULT_PORT)

        return self.async_create_entry(
            title=f"Autodarts ({board_name})",
            data=data,
        )
