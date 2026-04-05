"""The Autodarts integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AutodartsApiClient
from .const import CONF_HOST, CONF_PORT, PLATFORMS
from .coordinator import AutodartsDataUpdateCoordinator

type AutodartsConfigEntry = ConfigEntry[AutodartsDataUpdateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutodartsConfigEntry,
) -> bool:
    """Set up Autodarts from a config entry."""
    session = async_get_clientsession(hass)
    api = AutodartsApiClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        session=session,
    )

    coordinator = AutodartsDataUpdateCoordinator(hass, api)
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
