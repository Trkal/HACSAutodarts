"""API clients for Autodarts (local board + cloud)."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10

# Keycloak / OAuth2 constants
AUTH_URL = "https://login.autodarts.io/realms/autodarts/protocol/openid-connect/token"
API_BASE = "https://api.autodarts.io"


class AutodartsApiError(Exception):
    """Base exception for Autodarts API errors."""


class AutodartsConnectionError(AutodartsApiError):
    """Exception for connection errors."""


class AutodartsAuthError(AutodartsApiError):
    """Exception for authentication errors."""


# ---------------------------------------------------------------------------
# Local board API client (http://<board-ip>:3180)
# ---------------------------------------------------------------------------


class AutodartsLocalClient:
    """Async client for the Autodarts local board API."""

    def __init__(self, host: str, port: int, session: aiohttp.ClientSession) -> None:
        """Initialize the local API client."""
        self._session = session
        self._base_url = f"http://{host}:{port}"

    async def _request(self, path: str) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self._session.get(url)
                response.raise_for_status()
                return await response.json()
        except asyncio.TimeoutError as err:
            raise AutodartsConnectionError(
                f"Timeout connecting to board at {self._base_url}"
            ) from err
        except aiohttp.ClientError as err:
            raise AutodartsConnectionError(
                f"Error communicating with board at {self._base_url}: {err}"
            ) from err

    async def get_state(self) -> dict[str, Any]:
        """Get the current detection state (throws, status)."""
        return await self._request("/api/state")

    async def test_connection(self) -> bool:
        """Test if the board is reachable."""
        try:
            await self.get_state()
        except AutodartsApiError:
            return False
        return True


# ---------------------------------------------------------------------------
# Cloud API client (api.autodarts.io — OAuth2 / Keycloak)
# ---------------------------------------------------------------------------


class AutodartsCloudClient:
    """Async client for the Autodarts cloud API with OAuth2 auth."""

    def __init__(self, email: str, password: str, session: aiohttp.ClientSession) -> None:
        """Initialize the cloud API client."""
        self._email = email
        self._password = password
        self._session = session
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expiry: float = 0

    # -- authentication -----------------------------------------------------

    async def authenticate(self) -> None:
        """Obtain an access token using email + password."""
        data = {
            "grant_type": "password",
            "client_id": "autodarts-app",
            "username": self._email,
            "password": self._password,
        }
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                resp = await self._session.post(AUTH_URL, data=data)
                if resp.status == 401:
                    raise AutodartsAuthError("Invalid email or password")
                resp.raise_for_status()
                body = await resp.json()
        except asyncio.TimeoutError as err:
            raise AutodartsConnectionError("Timeout during authentication") from err
        except aiohttp.ClientError as err:
            raise AutodartsConnectionError(f"Auth request failed: {err}") from err

        self._access_token = body["access_token"]
        self._refresh_token = body.get("refresh_token")
        self._token_expiry = time.monotonic() + body.get("expires_in", 300) - 30

    async def _ensure_token(self) -> None:
        """Refresh the token if it is about to expire."""
        if self._access_token and time.monotonic() < self._token_expiry:
            return
        if self._refresh_token:
            try:
                await self._do_refresh()
                return
            except AutodartsApiError:
                _LOGGER.debug("Token refresh failed, re-authenticating")
        await self.authenticate()

    async def _do_refresh(self) -> None:
        data = {
            "grant_type": "refresh_token",
            "client_id": "autodarts-app",
            "refresh_token": self._refresh_token,
        }
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                resp = await self._session.post(AUTH_URL, data=data)
                resp.raise_for_status()
                body = await resp.json()
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            raise AutodartsConnectionError(f"Token refresh failed: {err}") from err

        self._access_token = body["access_token"]
        self._refresh_token = body.get("refresh_token", self._refresh_token)
        self._token_expiry = time.monotonic() + body.get("expires_in", 300) - 30

    async def _headers(self) -> dict[str, str]:
        await self._ensure_token()
        return {"Authorization": f"Bearer {self._access_token}"}

    # -- API requests --------------------------------------------------------

    async def _get(self, path: str) -> Any:
        url = f"{API_BASE}{path}"
        headers = await self._headers()
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                resp = await self._session.get(url, headers=headers)
                resp.raise_for_status()
                return await resp.json()
        except asyncio.TimeoutError as err:
            raise AutodartsConnectionError(f"Timeout fetching {path}") from err
        except aiohttp.ClientError as err:
            raise AutodartsConnectionError(f"Error fetching {path}: {err}") from err

    async def test_connection(self) -> bool:
        """Test authentication and cloud connectivity."""
        try:
            await self.authenticate()
            await self.get_boards()
        except AutodartsApiError:
            return False
        return True

    # -- boards --------------------------------------------------------------

    async def get_boards(self) -> list[dict[str, Any]]:
        """List all boards for the authenticated user."""
        return await self._get("/bs/v0/boards/")

    async def get_board(self, board_id: str) -> dict[str, Any]:
        """Get a single board by ID."""
        return await self._get(f"/bs/v0/boards/{board_id}")

    # -- matches -------------------------------------------------------------

    async def get_match(self, match_id: str) -> dict[str, Any]:
        """Get full match data including players, scores, turns."""
        return await self._get(f"/gs/v0/matches/{match_id}")

    # -- users / stats -------------------------------------------------------

    async def get_user(self, user_id: str) -> dict[str, Any]:
        """Get user profile."""
        return await self._get(f"/as/v0/users/{user_id}")

    async def get_user_stats(self, user_id: str, variant: str = "x01", limit: int = 10) -> dict[str, Any]:
        """Get user statistics for a game variant."""
        return await self._get(f"/as/v0/users/{user_id}/stats/{variant}?limit={limit}")
