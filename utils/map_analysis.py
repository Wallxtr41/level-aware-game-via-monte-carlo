from __future__ import annotations

from collections import deque

Grid = list[list[int]]
Position = tuple[int, int]


def copy_grid(grid: Grid) -> Grid:
    return [row[:] for row in grid]


def iter_neighbors(row: int, col: int) -> tuple[Position, ...]:
    return (
        (row - 1, col),
        (row, col + 1),
        (row + 1, col),
        (row, col - 1),
    )


def in_bounds(grid: Grid, row: int, col: int) -> bool:
    return 0 <= row < len(grid) and 0 <= col < len(grid[0])


def is_walkable(grid: Grid, row: int, col: int) -> bool:
    return in_bounds(grid, row, col) and grid[row][col] == 0


def bfs_distances(grid: Grid, start: Position) -> dict[Position, int]:
    return bfs_distances_with_blocked(grid, start, blocked_positions=set())


def bfs_distances_with_blocked(
    grid: Grid,
    start: Position,
    *,
    blocked_positions: set[Position],
) -> dict[Position, int]:
    start_row, start_col = start

    if not is_walkable(grid, start_row, start_col):
        return {}

    distances = {start: 0}
    queue = deque([start])

    while queue:
        row, col = queue.popleft()

        for next_row, next_col in iter_neighbors(row, col):
            if (next_row, next_col) in blocked_positions:
                continue

            if not is_walkable(grid, next_row, next_col):
                continue

            if (next_row, next_col) in distances:
                continue

            distances[(next_row, next_col)] = distances[(row, col)] + 1
            queue.append((next_row, next_col))

    return distances


def choose_farthest_reachable_cell(grid: Grid, start: Position) -> Position:
    distances = bfs_distances(grid, start)

    if not distances:
        raise ValueError("Map does not contain a reachable start cell.")

    return max(distances, key=distances.get)


def shortest_path_length(grid: Grid, start: Position, goal: Position) -> int | None:
    distances = bfs_distances(grid, start)
    return distances.get(goal)


def shortest_path_length_with_blocked(
    grid: Grid,
    start: Position,
    goal: Position,
    *,
    blocked_positions: set[Position],
) -> int | None:
    distances = bfs_distances_with_blocked(
        grid,
        start,
        blocked_positions=blocked_positions - {start, goal},
    )
    return distances.get(goal)


def render_ascii_grid(
    grid: Grid,
    start: Position | None = None,
    door: Position | None = None,
) -> str:
    lines = []

    for row_index, row in enumerate(grid):
        chars = []

        for col_index, cell in enumerate(row):
            position = (row_index, col_index)

            if start is not None and position == start:
                chars.append("S")
            elif door is not None and position == door:
                chars.append("D")
            elif cell == 0:
                chars.append(".")
            else:
                chars.append("#")

        lines.append(" ".join(chars))

    return "\n".join(lines)
