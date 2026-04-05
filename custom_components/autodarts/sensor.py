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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_HOST,
    CONF_PORT,
    DOMAIN,
    SENSOR_BOARD_STATUS,
    SENSOR_CURRENT_PLAYER,
    SENSOR_DARTS_THROWN,
    SENSOR_GAME_MODE,
    SENSOR_LAST_THROW,
    SENSOR_LAST_VISIT_SCORE,
    SENSOR_MATCH_STATE,
)
from .coordinator import AutodartsDataUpdateCoordinator
from .entity import AutodartsEntity


@dataclass(frozen=True, kw_only=True)
class AutodartsSensorEntityDescription(SensorEntityDescription):
    """Describe an Autodarts sensor."""

    value_fn: Callable[[dict[str, Any]], Any]


def _get_board_status(data: dict[str, Any]) -> str:
    """Extract board connection status."""
    return "connected" if data else "disconnected"


def _get_game_mode(data: dict[str, Any]) -> str | None:
    """Extract the current game mode."""
    game = data.get("game", {})
    return game.get("mode") or game.get("variant")


def _get_match_state(data: dict[str, Any]) -> str | None:
    """Extract match state."""
    return data.get("state") or data.get("status")


def _get_current_player(data: dict[str, Any]) -> str | None:
    """Extract the name of the current active player."""
    players = data.get("players", [])
    turn = data.get("player", data.get("turn", 0))
    if isinstance(turn, int) and 0 <= turn < len(players):
        player = players[turn]
        return player.get("name", f"Player {turn + 1}")
    return None


def _get_last_throw(data: dict[str, Any]) -> str | None:
    """Extract the last throw description (e.g. 'T20', 'D16', 'S5')."""
    turns = data.get("turns", [])
    if not turns:
        return None
    last_turn = turns[-1] if isinstance(turns, list) else None
    if not last_turn:
        return None
    throws = last_turn.get("throws", [])
    if not throws:
        return None
    last = throws[-1]
    if isinstance(last, dict):
        segment = last.get("segment", {})
        name = segment.get("name") or segment.get("display")
        if name:
            return str(name)
        # Build from number and multiplier
        number = segment.get("number", last.get("number", ""))
        multiplier = segment.get("multiplier", last.get("multiplier", 1))
        if number == 25:
            return "Bull" if multiplier == 1 else "D-Bull"
        prefix = {1: "S", 2: "D", 3: "T"}.get(multiplier, "")
        return f"{prefix}{number}" if number else None
    return str(last) if last else None


def _get_last_visit_score(data: dict[str, Any]) -> int | None:
    """Extract the total score of the last visit (last 3 darts)."""
    turns = data.get("turns", [])
    if not turns:
        return None
    last_turn = turns[-1] if isinstance(turns, list) else None
    if not last_turn:
        return None
    # Try direct points field first
    points = last_turn.get("points")
    if points is not None:
        return int(points)
    # Sum individual throws
    throws = last_turn.get("throws", [])
    total = 0
    for throw in throws:
        if isinstance(throw, dict):
            total += throw.get("points", throw.get("score", 0))
        elif isinstance(throw, (int, float)):
            total += int(throw)
    return total if throws else None


def _get_darts_thrown(data: dict[str, Any]) -> int | None:
    """Extract total number of darts thrown in the match."""
    darts = data.get("dartsThrown") or data.get("darts_thrown")
    if darts is not None:
        return int(darts)
    # Count from turns
    turns = data.get("turns", [])
    total = 0
    for turn in turns:
        if isinstance(turn, dict):
            total += len(turn.get("throws", []))
    return total if turns else None


STATIC_SENSORS: tuple[AutodartsSensorEntityDescription, ...] = (
    AutodartsSensorEntityDescription(
        key=SENSOR_BOARD_STATUS,
        translation_key=SENSOR_BOARD_STATUS,
        icon="mdi:bullseye",
        value_fn=_get_board_status,
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
        key=SENSOR_CURRENT_PLAYER,
        translation_key=SENSOR_CURRENT_PLAYER,
        icon="mdi:account",
        value_fn=_get_current_player,
    ),
    AutodartsSensorEntityDescription(
        key=SENSOR_LAST_THROW,
        translation_key=SENSOR_LAST_THROW,
        icon="mdi:arrow-projectile",
        value_fn=_get_last_throw,
    ),
    AutodartsSensorEntityDescription(
        key=SENSOR_LAST_VISIT_SCORE,
        translation_key=SENSOR_LAST_VISIT_SCORE,
        icon="mdi:numeric",
        native_unit_of_measurement="points",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_get_last_visit_score,
    ),
    AutodartsSensorEntityDescription(
        key=SENSOR_DARTS_THROWN,
        translation_key=SENSOR_DARTS_THROWN,
        icon="mdi:counter",
        native_unit_of_measurement="darts",
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
    board_id = f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"

    entities: list[SensorEntity] = []

    # Static sensors (always present)
    for description in STATIC_SENSORS:
        entities.append(
            AutodartsSensor(coordinator, board_id, description)
        )

    # Dynamic per-player sensors
    data = coordinator.data or {}
    players = data.get("players", [])
    for idx, player in enumerate(players):
        player_name = player.get("name", f"Player {idx + 1}")
        entities.extend(
            _create_player_sensors(coordinator, board_id, idx, player_name)
        )

    async_add_entities(entities)

    # Listen for new players appearing in future updates
    _track_new_players(coordinator, board_id, async_add_entities, len(players))


def _create_player_sensors(
    coordinator: AutodartsDataUpdateCoordinator,
    board_id: str,
    player_index: int,
    player_name: str,
) -> list[SensorEntity]:
    """Create the set of sensors for a single player."""
    return [
        AutodartsPlayerScoreSensor(
            coordinator, board_id, player_index, player_name
        ),
        AutodartsPlayerPPDSensor(
            coordinator, board_id, player_index, player_name
        ),
        AutodartsPlayerLegsSensor(
            coordinator, board_id, player_index, player_name
        ),
    ]


def _track_new_players(
    coordinator: AutodartsDataUpdateCoordinator,
    board_id: str,
    async_add_entities: AddEntitiesCallback,
    known_count: int,
) -> None:
    """Track coordinator updates and add sensors when new players appear."""
    tracked = {"count": known_count}

    @callback
    def _check_for_new_players() -> None:
        data = coordinator.data or {}
        players = data.get("players", [])
        if len(players) > tracked["count"]:
            new_entities: list[SensorEntity] = []
            for idx in range(tracked["count"], len(players)):
                player_name = players[idx].get("name", f"Player {idx + 1}")
                new_entities.extend(
                    _create_player_sensors(
                        coordinator, board_id, idx, player_name
                    )
                )
            tracked["count"] = len(players)
            async_add_entities(new_entities)

    coordinator.async_add_listener(_check_for_new_players)


# ---------------------------------------------------------------------------
# Sensor entity classes
# ---------------------------------------------------------------------------


class AutodartsSensor(AutodartsEntity, SensorEntity):
    """Representation of a static Autodarts sensor."""

    entity_description: AutodartsSensorEntityDescription

    def __init__(
        self,
        coordinator: AutodartsDataUpdateCoordinator,
        board_id: str,
        description: AutodartsSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, board_id)
        self.entity_description = description
        self._attr_unique_id = f"{board_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data or {})


class AutodartsPlayerSensorBase(AutodartsEntity, SensorEntity):
    """Base class for per-player sensors."""

    def __init__(
        self,
        coordinator: AutodartsDataUpdateCoordinator,
        board_id: str,
        player_index: int,
        player_name: str,
        key_suffix: str,
    ) -> None:
        """Initialize the player sensor."""
        super().__init__(coordinator, board_id)
        self._player_index = player_index
        self._player_name = player_name
        self._attr_unique_id = f"{board_id}_player_{player_index}_{key_suffix}"

    def _get_player_data(self) -> dict[str, Any]:
        """Get the data dict for this player."""
        data = self.coordinator.data or {}
        players = data.get("players", [])
        if self._player_index < len(players):
            return players[self._player_index]
        return {}


class AutodartsPlayerScoreSensor(AutodartsPlayerSensorBase):
    """Sensor for a player's current score."""

    _attr_icon = "mdi:counter"
    _attr_native_unit_of_measurement = "points"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: AutodartsDataUpdateCoordinator,
        board_id: str,
        player_index: int,
        player_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, board_id, player_index, player_name, "score")
        self._attr_name = f"{player_name} Score"

    @property
    def native_value(self) -> int | None:
        """Return the player's current score."""
        player = self._get_player_data()
        return player.get("score") or player.get("remaining")


class AutodartsPlayerPPDSensor(AutodartsPlayerSensorBase):
    """Sensor for a player's Points Per Dart average."""

    _attr_icon = "mdi:chart-line"
    _attr_native_unit_of_measurement = "PPD"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: AutodartsDataUpdateCoordinator,
        board_id: str,
        player_index: int,
        player_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, board_id, player_index, player_name, "ppd")
        self._attr_name = f"{player_name} PPD"

    @property
    def native_value(self) -> float | None:
        """Return the player's PPD average."""
        player = self._get_player_data()
        ppd = player.get("ppd") or player.get("average")
        if ppd is not None:
            return round(float(ppd), 2)
        # Calculate from stats if available
        stats = player.get("stats", {})
        avg = stats.get("ppd") or stats.get("average") or stats.get("avg")
        if avg is not None:
            return round(float(avg), 2)
        return None


class AutodartsPlayerLegsSensor(AutodartsPlayerSensorBase):
    """Sensor for a player's legs/sets won."""

    _attr_icon = "mdi:trophy"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coordinator: AutodartsDataUpdateCoordinator,
        board_id: str,
        player_index: int,
        player_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, board_id, player_index, player_name, "legs")
        self._attr_name = f"{player_name} Legs Won"

    @property
    def native_value(self) -> int | None:
        """Return the number of legs won."""
        player = self._get_player_data()
        legs = player.get("legsWon") or player.get("legs_won") or player.get("legs")
        if legs is not None:
            return int(legs)
        return None
