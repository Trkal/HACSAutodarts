"""Constants for the Autodarts integration."""

from typing import Final

DOMAIN: Final = "autodarts"

DEFAULT_PORT: Final = 3180
DEFAULT_SCAN_INTERVAL: Final = 5  # seconds

CONF_HOST: Final = "host"
CONF_PORT: Final = "port"

PLATFORMS: Final = ["sensor"]

# Sensor keys
SENSOR_BOARD_STATUS: Final = "board_status"
SENSOR_GAME_MODE: Final = "game_mode"
SENSOR_MATCH_STATE: Final = "match_state"
SENSOR_CURRENT_PLAYER: Final = "current_player"
SENSOR_LAST_THROW: Final = "last_throw"
SENSOR_LAST_VISIT_SCORE: Final = "last_visit_score"
SENSOR_DARTS_THROWN: Final = "darts_thrown"
