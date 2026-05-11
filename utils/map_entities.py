from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Literal, Sequence

from utils.map_analysis import choose_farthest_reachable_cell
from utils.maze_generation import EXTRA_CONNECTION_CHANCE, generate_maze_map

Grid = list[list[int]]
Position = tuple[int, int]
ItemKind = Literal["stamina", "power", "key"]

START_POS: Position = (1, 1)
DEFAULT_ITEM_KINDS: tuple[ItemKind, ...] = ("stamina", "power", "key")


@dataclass(frozen=True)
class ItemPlacement:
    kind: ItemKind
    position: Position


@dataclass(frozen=True)
class MazeLayout:
    grid: Grid
    start: Position
    door: Position
    items: tuple[ItemPlacement, ...]


def choose_door_position(grid: Grid, start: Position = START_POS) -> Position:
    return choose_farthest_reachable_cell(grid, start)


def get_walkable_positions(
    grid: Grid,
    blocked_positions: set[Position] | None = None,
) -> list[Position]:
    blocked_positions = blocked_positions or set()
    positions: list[Position] = []

    for row_index, row in enumerate(grid):
        for col_index, cell in enumerate(row):
            position = (row_index, col_index)

            if cell != 0 or position in blocked_positions:
                continue

            positions.append(position)

    return positions


def place_items(
    grid: Grid,
    item_kinds: Sequence[ItemKind] = DEFAULT_ITEM_KINDS,
    start: Position = START_POS,
    door: Position | None = None,
    rng: random.Random | None = None,
) -> tuple[ItemPlacement, ...]:
    blocked_positions = {start}

    if door is not None:
        blocked_positions.add(door)

    walkable_positions = get_walkable_positions(grid, blocked_positions=blocked_positions)

    if len(walkable_positions) < len(item_kinds):
        raise ValueError("Not enough walkable cells to place all items.")

    rng = rng or random
    selected_positions = rng.sample(walkable_positions, k=len(item_kinds))

    return tuple(
        ItemPlacement(kind=item_kind, position=position)
        for item_kind, position in zip(item_kinds, selected_positions, strict=True)
    )


def generate_maze_layout(
    width: int,
    height: int,
    *,
    start: Position = START_POS,
    extra_connection_chance: float = EXTRA_CONNECTION_CHANCE,
    item_kinds: Sequence[ItemKind] = DEFAULT_ITEM_KINDS,
    rng: random.Random | None = None,
) -> MazeLayout:
    grid = generate_maze_map(
        width=width,
        height=height,
        extra_connection_chance=extra_connection_chance,
    )
    door = choose_door_position(grid, start)
    items = place_items(grid, item_kinds=item_kinds, start=start, door=door, rng=rng)
    return MazeLayout(grid=grid, start=start, door=door, items=items)
