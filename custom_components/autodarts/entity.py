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
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        board = coordinator.data.get("board", {}) if coordinator.data else {}
        board_name = board.get("name", "Autodarts Board")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.board_id)},
            name=board_name,
            manufacturer="Autodarts",
            model="Dart Board",
        )
