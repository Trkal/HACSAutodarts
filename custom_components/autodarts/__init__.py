"""The Autodarts integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AutodartsCloudClient, AutodartsLocalClient
from .const import CONF_BOARD_ID, CONF_HOST, CONF_PORT, CONF_TOKEN, PLATFORMS
from .coordinator import AutodartsDataUpdateCoordinator

type AutodartsConfigEntry = ConfigEntry[AutodartsDataUpdateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutodartsConfigEntry,
) -> bool:
    """Set up Autodarts from a config entry."""
    session = async_get_clientsession(hass)

    cloud = AutodartsCloudClient(
        session=session,
        token=entry.data[CONF_TOKEN],
    )

    local = None
    if entry.data.get(CONF_HOST):
        local = AutodartsLocalClient(
            host=entry.data[CONF_HOST],
            port=entry.data.get(CONF_PORT, 3180),
            session=session,
        )

    coordinator = AutodartsDataUpdateCoordinator(
        hass,
        cloud=cloud,
        board_id=entry.data[CONF_BOARD_ID],
        local=local,
        entry=entry,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: AutodartsConfigEntry,
) -> bool:
    """Unload an Autodarts config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
