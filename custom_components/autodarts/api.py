"""API client for the Autodarts local board."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 5


class AutodartsApiError(Exception):
    """Base exception for Autodarts API errors."""


class AutodartsConnectionError(AutodartsApiError):
    """Exception for connection errors."""


class AutodartsApiClient:
    """Async client for the Autodarts local board API."""

    def __init__(
        self,
        host: str,
        port: int,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the API client."""
        self._host = host
        self._port = port
        self._session = session
        self._base_url = f"http://{host}:{port}"

    async def _request(self, path: str) -> dict[str, Any]:
        """Make a GET request to the board API."""
        url = f"{self._base_url}{path}"
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self._session.get(url)
                response.raise_for_status()
                return await response.json()
        except asyncio.TimeoutError as err:
            raise AutodartsConnectionError(
                f"Timeout connecting to Autodarts board at {self._base_url}"
            ) from err
        except aiohttp.ClientError as err:
            raise AutodartsConnectionError(
                f"Error communicating with Autodarts board at {self._base_url}: {err}"
            ) from err

    async def get_state(self) -> dict[str, Any]:
        """Get the current game state (scores, players, throws)."""
        return await self._request("/api/state")

    async def get_config(self) -> dict[str, Any]:
        """Get the board configuration."""
        return await self._request("/api/config")

    async def get_host(self) -> dict[str, Any]:
        """Get host/system information."""
        return await self._request("/api/host")

    async def get_version(self) -> dict[str, Any]:
        """Get the software version."""
        return await self._request("/api/version")

    async def test_connection(self) -> bool:
        """Test if the board is reachable."""
        try:
            await self.get_state()
        except AutodartsApiError:
            return False
        return True
