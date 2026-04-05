"""Base entity for the Autodarts integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AutodartsDataUpdateCoordinator


class AutodartsEntity(CoordinatorEntity[AutodartsDataUpdateCoordinator]):
    """Base class for Autodarts entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AutodartsDataUpdateCoordinator,
        board_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._board_id = board_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, board_id)},
            name="Autodarts Board",
            manufacturer="Autodarts",
            model="Dart Board",
        )
