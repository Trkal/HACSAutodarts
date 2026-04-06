"""Sensor platform for the Autodarts integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SENSOR_BOARD_EVENT,
    SENSOR_BOARD_STATUS,
    SENSOR_DARTS_THROWN,
    SENSOR_GAME_MODE,
    SENSOR_LAST_THROW,
    SENSOR_MATCH_STATE,
    SENSOR_NUM_THROWS,
    SENSOR_ROUND,
    SENSOR_VISIT_SCORE,
)
from .coordinator import AutodartsDataUpdateCoordinator
from .entity import AutodartsEntity


# ---------------------------------------------------------------------------
# Helpers to extract values from coordinator data
# ---------------------------------------------------------------------------
# coordinator.data = {"board": {...}, "match": {...} | None, "local": {...}}

def _board(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("board") or {}


def _match(data: dict[str, Any]) -> dict[str, Any] | None:
    return data.get("match")


def _local(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("local") or {}


# -- value extractors -------------------------------------------------------

def _get_board_status(data: dict[str, Any]) -> str:
    """Board connected / disconnected (from cloud board state)."""
    board = _board(data)
    state = board.get("state") or {}
    if state.get("connected"):
        return "connected"
    return "disconnected"


def _get_board_event(data: dict[str, Any]) -> str | None:
    """Last board event from local detection or cloud."""
    local = _local(data)
    if local:
        return local.get("status") or local.get("event")
    board = _board(data)
    state = board.get("state") or {}
    return state.get("event") or board.get("status")


def _get_game_mode(data: dict[str, Any]) -> str | None:
    """Game variant (X01, Cricket, etc.) from match."""
    match = _match(data)
    if not match:
        return None
    return match.get("variant")


def _get_match_state(data: dict[str, Any]) -> str | None:
    """Match state — active / finished / etc."""
    match = _match(data)
    if not match:
        return "No match"
    if match.get("finished"):
        return "Finished"
    return "Active"


def _get_round(data: dict[str, Any]) -> int | None:
    """Current round number."""
    match = _match(data)
    if not match:
        return None
    return match.get("round")


def _get_last_throw(data: dict[str, Any]) -> str | None:
    """Last detected throw segment name (e.g. T20, D16, S5, M2)."""
    local = _local(data)
    throws = local.get("throws", [])
    if throws:
        last = throws[-1]
        segment = last.get("segment", {})
        return segment.get("name")
    return None


def _get_num_throws(data: dict[str, Any]) -> int | None:
    """Number of throws in the current turn (from local board, 0–3)."""
    local = _local(data)
    if local:
        return local.get("numThrows")
    return None


def _get_visit_score(data: dict[str, Any]) -> int | None:
    """Total score of the current turn/visit."""
    match = _match(data)
    if not match:
        return None
    return match.get("turnScore")


def _get_darts_thrown(data: dict[str, Any]) -> int | None:
    """Total darts thrown in the match (across all players)."""
    match = _match(data)
    if not match:
        return None
    turns = match.get("turns")
    if isinstance(turns, list):
        return sum(len(t.get("throws", [])) for t in turns)
    return None


# ---------------------------------------------------------------------------
# Sensor descriptions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class AutodartsSensorEntityDescription(SensorEntityDescription):
    """Describe an Autodarts sensor."""

    value_fn: Callable[[dict[str, Any]], Any]


STATIC_SENSORS: tuple[AutodartsSensorEntityDescription, ...] = (
    AutodartsSensorEntityDescription(
        key=SENSOR_BOARD_STATUS,
        translation_key=SENSOR_BOARD_STATUS,
        icon="mdi:bullseye",
        value_fn=_get_board_status,
    ),
    AutodartsSensorEntityDescription(
        key=SENSOR_BOARD_EVENT,
        translation_key=SENSOR_BOARD_EVENT,
        icon="mdi:bell-ring",
        value_fn=_get_board_event,
    ),
    AutodartsSensorEntityDescription(
        key=SENSOR_GAME_MODE,
        translation_key=SENSOR_GAME_MODE,
        icon="mdi:gamepad-variant",
        value_fn=_get_game_mode,
    ),
    AutodartsSensorEntityDescription(
        key=SENSOR_MATCH_STATE,
        translation_key=SENSOR_MATCH_STATE,
        icon="mdi:play-circle",
        value_fn=_get_match_state,
    ),
    AutodartsSensorEntityDescription(
        key=SENSOR_ROUND,
        translation_key=SENSOR_ROUND,
        icon="mdi:rotate-right",
        value_fn=_get_round,
    ),
    AutodartsSensorEntityDescription(
        key=SENSOR_LAST_THROW,
        translation_key=SENSOR_LAST_THROW,
        icon="mdi:arrow-projectile",
        value_fn=_get_last_throw,
    ),
    AutodartsSensorEntityDescription(
        key=SENSOR_NUM_THROWS,
        translation_key=SENSOR_NUM_THROWS,
        icon="mdi:counter",
        native_unit_of_measurement="darts",
        value_fn=_get_num_throws,
    ),
    AutodartsSensorEntityDescription(
        key=SENSOR_VISIT_SCORE,
        translation_key=SENSOR_VISIT_SCORE,
        icon="mdi:numeric",
        native_unit_of_measurement="points",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_get_visit_score,
    ),
    AutodartsSensorEntityDescription(
        key=SENSOR_DARTS_THROWN,
        translation_key=SENSOR_DARTS_THROWN,
        icon="mdi:counter",
        native_unit_of_measurement="turns",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_get_darts_thrown,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Autodarts sensors from a config entry."""
    coordinator: AutodartsDataUpdateCoordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        AutodartsSensor(coordinator, description)
        for description in STATIC_SENSORS
    ]

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Sensor entity classes
# ---------------------------------------------------------------------------


class AutodartsSensor(AutodartsEntity, SensorEntity):
    """Representation of a static Autodarts sensor."""

    entity_description: AutodartsSensorEntityDescription

    def __init__(
        self,
        coordinator: AutodartsDataUpdateCoordinator,
        description: AutodartsSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.board_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data or {})
