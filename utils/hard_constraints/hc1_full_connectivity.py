"""Hard Constraint 1: all walkable cells must form one connected component."""

from __future__ import annotations

from collections import deque

Grid = list[list[int]]


def _is_walkable(value: int, walkable_values: tuple[int, ...]) -> bool:
    return value in walkable_values


def _in_bounds(grid: Grid, row: int, col: int) -> bool:
    return 0 <= row < len(grid) and 0 <= col < len(grid[0])


def _iter_neighbors(row: int, col: int) -> tuple[tuple[int, int], ...]:
    return (
        (row - 1, col),
        (row, col + 1),
        (row + 1, col),
        (row, col - 1),
    )


def count_walkable_neighbors(
    grid: Grid,
    row: int,
    col: int,
    walkable_values: tuple[int, ...] = (0,),
) -> int:
    """Return how many 4-neighbor cells are walkable around one position."""
    if not grid or not grid[0]:
        return 0

    count = 0

    for next_row, next_col in _iter_neighbors(row, col):
        if _in_bounds(grid, next_row, next_col) and _is_walkable(
            grid[next_row][next_col],
            walkable_values,
        ):
            count += 1

    return count


def _count_walkable_cells(grid: Grid, walkable_values: tuple[int, ...]) -> int:
    return sum(1 for row in grid for cell in row if _is_walkable(cell, walkable_values))


def get_reachable_walkable_count(
    grid: Grid,
    start_row: int,
    start_col: int,
    walkable_values: tuple[int, ...] = (0,),
) -> int:
    """Run BFS from the start cell and count reachable walkable cells."""
    if not grid or not grid[0]:
        return 0

    if not _in_bounds(grid, start_row, start_col):
        return 0

    if not _is_walkable(grid[start_row][start_col], walkable_values):
        return 0

    visited: set[tuple[int, int]] = {(start_row, start_col)}
    queue = deque([(start_row, start_col)])

    while queue:
        row, col = queue.popleft()

        for next_row, next_col in _iter_neighbors(row, col):
            if not _in_bounds(grid, next_row, next_col):
                continue

            if (next_row, next_col) in visited:
                continue

            if not _is_walkable(grid[next_row][next_col], walkable_values):
                continue

            visited.add((next_row, next_col))
            queue.append((next_row, next_col))

    return len(visited)


def is_hc1_satisfied(
    grid: Grid,
    start_row: int,
    start_col: int,
    walkable_values: tuple[int, ...] = (0,),
) -> bool:
    """Return True when every walkable cell is reachable from the start cell."""
    total_walkable = _count_walkable_cells(grid, walkable_values)

    if total_walkable == 0:
        return False

    reachable_walkable = get_reachable_walkable_count(
        grid,
        start_row,
        start_col,
        walkable_values,
    )
    return reachable_walkable == total_walkable


def can_open_cell_preserve_connectivity(
    grid: Grid,
    row: int,
    col: int,
    walkable_values: tuple[int, ...] = (0,),
) -> bool:
    """Cheap local check for wall -> road.

    Assuming the current map is already HC1-valid, opening one blocked cell
    preserves connectivity exactly when the new cell touches at least one
    existing walkable cell.
    """
    if not grid or not grid[0]:
        return False

    if not _in_bounds(grid, row, col):
        raise IndexError("Cell position is outside the grid.")

    if _is_walkable(grid[row][col], walkable_values):
        return True

    return count_walkable_neighbors(grid, row, col, walkable_values) >= 1


def can_remove_cell_preserve_connectivity(
    grid: Grid,
    row: int,
    col: int,
    walkable_values: tuple[int, ...] = (0,),
) -> bool:
    """Cheap local check for road -> wall.

    If the cell is a leaf or isolated node in the current graph, removing it
    cannot disconnect the remaining walkable cells. Otherwise, run a full BFS
    on the candidate map before deciding.
    """
    if not grid or not grid[0]:
        return False

    if not _in_bounds(grid, row, col):
        raise IndexError("Cell position is outside the grid.")

    if not _is_walkable(grid[row][col], walkable_values):
        return True

    return count_walkable_neighbors(grid, row, col, walkable_values) <= 1
