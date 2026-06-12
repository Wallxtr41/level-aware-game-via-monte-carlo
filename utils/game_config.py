from __future__ import annotations

from dataclasses import dataclass


MIN_TARGET_AGENT_DIFFICULTY = 0.0
MAX_TARGET_AGENT_DIFFICULTY = 1.0
MIN_PLAYER_VISION_RADIUS = 1
MAX_PLAYER_VISION_RADIUS = 5
MIN_GRID_WIDTH = 9
MAX_GRID_WIDTH = 31
MIN_GRID_HEIGHT = 9
MAX_GRID_HEIGHT = 25
MIN_STAMINA_ITEM_COUNT = 0
MAX_STAMINA_ITEM_COUNT = 3
MIN_STAMINA_ITEM_VALUE = 1
MAX_STAMINA_ITEM_VALUE = 50

TARGET_AGENT_DIFFICULTY = 0.5
PLAYER_VISION_RADIUS = 1
GRID_WIDTH = 15
GRID_HEIGHT = 15
DOOR_REQUIRES_KEY = True
STAMINA_ITEM_COUNT = 2
STAMINA_ITEM_VALUE = 15


@dataclass(frozen=True)
class DifficultyStaminaConfig:
    target_agent_difficulty: float = TARGET_AGENT_DIFFICULTY
    player_vision_radius: int = PLAYER_VISION_RADIUS
    grid_width: int = GRID_WIDTH
    grid_height: int = GRID_HEIGHT
    door_requires_key: bool = DOOR_REQUIRES_KEY
    stamina_item_count: int = STAMINA_ITEM_COUNT
    stamina_item_value: int = STAMINA_ITEM_VALUE


def clamp_difficulty_stamina_config(
    config: DifficultyStaminaConfig,
) -> DifficultyStaminaConfig:
    return DifficultyStaminaConfig(
        target_agent_difficulty=_clamp_float(
            config.target_agent_difficulty,
            MIN_TARGET_AGENT_DIFFICULTY,
            MAX_TARGET_AGENT_DIFFICULTY,
        ),
        player_vision_radius=_clamp_int(
            config.player_vision_radius,
            MIN_PLAYER_VISION_RADIUS,
            MAX_PLAYER_VISION_RADIUS,
        ),
        grid_width=_clamp_odd(
            config.grid_width,
            MIN_GRID_WIDTH,
            MAX_GRID_WIDTH,
        ),
        grid_height=_clamp_odd(
            config.grid_height,
            MIN_GRID_HEIGHT,
            MAX_GRID_HEIGHT,
        ),
        door_requires_key=bool(config.door_requires_key),
        stamina_item_count=_clamp_int(
            config.stamina_item_count,
            MIN_STAMINA_ITEM_COUNT,
            MAX_STAMINA_ITEM_COUNT,
        ),
        stamina_item_value=_clamp_int(
            config.stamina_item_value,
            MIN_STAMINA_ITEM_VALUE,
            MAX_STAMINA_ITEM_VALUE,
        ),
    )


def get_difficulty_stamina_config() -> DifficultyStaminaConfig:
    return DifficultyStaminaConfig(
        target_agent_difficulty=TARGET_AGENT_DIFFICULTY,
        player_vision_radius=PLAYER_VISION_RADIUS,
        grid_width=GRID_WIDTH,
        grid_height=GRID_HEIGHT,
        door_requires_key=DOOR_REQUIRES_KEY,
        stamina_item_count=STAMINA_ITEM_COUNT,
        stamina_item_value=STAMINA_ITEM_VALUE,
    )


def apply_difficulty_stamina_config(config: DifficultyStaminaConfig) -> DifficultyStaminaConfig:
    global TARGET_AGENT_DIFFICULTY
    global PLAYER_VISION_RADIUS
    global GRID_WIDTH
    global GRID_HEIGHT
    global DOOR_REQUIRES_KEY
    global STAMINA_ITEM_COUNT
    global STAMINA_ITEM_VALUE

    config = clamp_difficulty_stamina_config(config)
    TARGET_AGENT_DIFFICULTY = config.target_agent_difficulty
    PLAYER_VISION_RADIUS = config.player_vision_radius
    GRID_WIDTH = config.grid_width
    GRID_HEIGHT = config.grid_height
    DOOR_REQUIRES_KEY = config.door_requires_key
    STAMINA_ITEM_COUNT = config.stamina_item_count
    STAMINA_ITEM_VALUE = config.stamina_item_value
    return config


def build_stamina_item_kinds(config: DifficultyStaminaConfig | None = None) -> tuple[str, ...]:
    config = config or get_difficulty_stamina_config()
    item_kinds = tuple("stamina" for _ in range(config.stamina_item_count))

    if config.door_requires_key:
        item_kinds = (*item_kinds, "key")

    return item_kinds


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, float(value)))


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return min(maximum, max(minimum, int(value)))


def _clamp_odd(value: int, minimum: int, maximum: int) -> int:
    value = _clamp_int(value, minimum, maximum)

    if value % 2 == 0:
        value += 1

    if value > maximum:
        value -= 2

    return max(minimum, value)
