"""API clients for Autodarts (local board + cloud)."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10

# Keycloak / OAuth2 constants
CLIENT_ID = "autodarts-play"
AUTH_URL = "https://login.autodarts.io/realms/autodarts/protocol/openid-connect/auth"
TOKEN_URL = "https://login.autodarts.io/realms/autodarts/protocol/openid-connect/token"
REDIRECT_URI = "https://play.autodarts.io/hacs-auth"
API_BASE = "https://api.autodarts.io"


class AutodartsApiError(Exception):
    """Base exception for Autodarts API errors."""


class AutodartsConnectionError(AutodartsApiError):
    """Exception for connection errors."""


class AutodartsAuthError(AutodartsApiError):
    """Exception for authentication errors."""


# ---------------------------------------------------------------------------
# OAuth2 helpers (Authorization Code + PKCE)
# ---------------------------------------------------------------------------


def generate_pkce() -> tuple[str, str]:
    """Generate a PKCE code_verifier and code_challenge (S256)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    import base64

    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_authorize_url(code_challenge: str) -> str:
    """Build the Keycloak authorization URL for the user to open."""
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "openid",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(
    session: aiohttp.ClientSession,
    code: str,
    code_verifier: str,
) -> dict[str, Any]:
    """Exchange an authorization code for tokens."""
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }
    try:
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            resp = await session.post(TOKEN_URL, data=data)
            if resp.status in (400, 401):
                body = await resp.json()
                raise AutodartsAuthError(
                    body.get("error_description", "Token exchange failed")
                )
            resp.raise_for_status()
            return await resp.json()
    except asyncio.TimeoutError as err:
        raise AutodartsConnectionError("Timeout during token exchange") from err
    except aiohttp.ClientError as err:
        raise AutodartsConnectionError(f"Token exchange failed: {err}") from err


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
    """Async client for the Autodarts cloud API with token-based auth."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: dict[str, Any],
    ) -> None:
        """Initialize the cloud API client with an existing token dict."""
        self._session = session
        self._access_token: str = token["access_token"]
        self._refresh_token: str | None = token.get("refresh_token")
        self._token_expiry: float = token.get("expires_at", 0)

    @property
    def token(self) -> dict[str, Any]:
        """Return the current token dict for persistence."""
        return {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "expires_at": self._token_expiry,
        }

    # -- authentication -----------------------------------------------------

    async def _ensure_token(self) -> None:
        """Refresh the token if it is about to expire."""
        if time.time() < self._token_expiry - 30:
            return
        if not self._refresh_token:
            raise AutodartsAuthError("No refresh token available — re-authenticate")
        await self._do_refresh()

    async def _do_refresh(self) -> None:
        data = {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": self._refresh_token,
        }
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                resp = await self._session.post(TOKEN_URL, data=data)
                if resp.status in (400, 401):
                    raise AutodartsAuthError("Refresh token expired — re-authenticate")
                resp.raise_for_status()
                body = await resp.json()
        except asyncio.TimeoutError as err:
            raise AutodartsConnectionError("Timeout refreshing token") from err
        except aiohttp.ClientError as err:
            raise AutodartsConnectionError(f"Token refresh failed: {err}") from err

        self._access_token = body["access_token"]
        self._refresh_token = body.get("refresh_token", self._refresh_token)
        self._token_expiry = time.time() + body.get("expires_in", 300)

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

    # -- boards --------------------------------------------------------------

    async def get_boards(self) -> list[dict[str, Any]]:
        """List all boards for the authenticated user."""
        return await self._get("/bs/v0/boards/")

    async def get_board(self, board_id: str) -> dict[str, Any]:
        """Get a single board by ID."""
        return await self._get(f"/bs/v0/boards/{board_id}")

    # -- matches -------------------------------------------------------------

    async def get_match(self, match_id: str) -> dict[str, Any]:
        """Get match metadata (players, variant, settings)."""
        return await self._get(f"/gs/v0/matches/{match_id}")

    async def get_match_state(self, match_id: str) -> dict[str, Any]:
        """Get live match game state (scores, turns, stats, etc.)."""
        return await self._get(f"/gs/v0/matches/{match_id}/state")

    # -- users / stats -------------------------------------------------------

    async def get_user(self, user_id: str) -> dict[str, Any]:
        """Get user profile."""
        return await self._get(f"/as/v0/users/{user_id}")

    async def get_user_stats(self, user_id: str, variant: str = "x01", limit: int = 10) -> dict[str, Any]:
        """Get user statistics for a game variant."""
        return await self._get(f"/as/v0/users/{user_id}/stats/{variant}?limit={limit}")
