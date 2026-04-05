"""Data update coordinator for Autodarts."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AutodartsApiClient, AutodartsApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AutodartsDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching Autodarts data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: AutodartsApiClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Autodarts board."""
        try:
            state = await self.api.get_state()
        except AutodartsApiError as err:
            raise UpdateFailed(f"Error fetching Autodarts data: {err}") from err

        return state
