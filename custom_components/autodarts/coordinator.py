"""Data update coordinator for Autodarts."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

import aiohttp

from .api import (
    AutodartsApiError,
    AutodartsCloudClient,
    AutodartsLocalClient,
)
from .const import CONF_TOKEN, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AutodartsDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching Autodarts data from cloud + local board."""

    def __init__(
        self,
        hass: HomeAssistant,
        cloud: AutodartsCloudClient,
        board_id: str,
        local: AutodartsLocalClient | None = None,
        entry: ConfigEntry | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.cloud = cloud
        self.board_id = board_id
        self.local = local
        self._entry = entry
        self._session = session

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from cloud API (and optionally local board)."""
        result: dict[str, Any] = {
            "board": {},
            "match": None,
            "local": {},
        }

        # 1. Cloud: get board state (includes matchId)
        try:
            board = await self.cloud.get_board(self.board_id)
            result["board"] = board
        except AutodartsApiError as err:
            raise UpdateFailed(f"Error fetching board data: {err}") from err

        # 2. Cloud: if a match is active, fetch match data
        match_id = board.get("matchId")
        if match_id:
            try:
                result["match"] = await self.cloud.get_match(match_id)
            except AutodartsApiError as err:
                _LOGGER.warning("Could not fetch match %s: %s", match_id, err)

        # 3. Local board: auto-discover from cloud if not configured
        if self.local is None and self._session is not None:
            board_ip = board.get("ip", "")
            if board_ip:
                from urllib.parse import urlparse

                parsed = urlparse(board_ip)
                host = parsed.hostname
                port = parsed.port or 3180
                if host:
                    self.local = AutodartsLocalClient(
                        host=host, port=port, session=self._session,
                    )
                    _LOGGER.debug("Auto-discovered local board at %s:%s", host, port)

        if self.local:
            try:
                result["local"] = await self.local.get_state()
            except AutodartsApiError:
                _LOGGER.debug("Local board not reachable")

        # 4. Persist refreshed token so it survives restarts
        if self._entry is not None:
            new_token = self.cloud.token
            stored = self._entry.data.get(CONF_TOKEN, {})
            if new_token.get("access_token") != stored.get("access_token"):
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    data={**self._entry.data, CONF_TOKEN: new_token},
                )

        return result
