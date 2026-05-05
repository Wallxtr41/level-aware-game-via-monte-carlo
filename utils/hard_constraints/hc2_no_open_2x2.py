"""Hard Constraint 2: reject maps that contain 2x2 open-cell blocks."""

from __future__ import annotations

from typing import Iterable

Grid = list[list[int]]


def _iter_affected_block_origins(
    row: int,
    col: int,
    height: int,
    width: int,
) -> Iterable[tuple[int, int]]:
    """Yield the top-left corners of 2x2 blocks that include (row, col)."""
    for row_offset in (-1, 0):
        for col_offset in (-1, 0):
            top_row = row + row_offset
            left_col = col + col_offset

            if 0 <= top_row < height - 1 and 0 <= left_col < width - 1:
                yield top_row, left_col


def _is_open(value: int, open_value: int) -> bool:
    return value == open_value


def _block_is_open_2x2(
    grid: Grid,
    top_row: int,
    left_col: int,
    open_value: int,
    override: tuple[int, int] | None = None,
) -> bool:
    for row in range(top_row, top_row + 2):
        for col in range(left_col, left_col + 2):
            cell_value = grid[row][col]

            if override == (row, col):
                cell_value = open_value

            if not _is_open(cell_value, open_value):
                return False

    return True


def find_open_2x2_blocks(grid: Grid, open_value: int = 0) -> list[tuple[int, int]]:
    """Return the top-left coordinates of every open 2x2 block in the grid."""
    if not grid or not grid[0]:
        return []

    height = len(grid)
    width = len(grid[0])
    violations: list[tuple[int, int]] = []

    for row in range(height - 1):
        for col in range(width - 1):
            if _block_is_open_2x2(grid, row, col, open_value):
                violations.append((row, col))

    return violations


def is_hc2_satisfied(grid: Grid, open_value: int = 0) -> bool:
    """Return True when the grid contains no open 2x2 block."""
    return not find_open_2x2_blocks(grid, open_value=open_value)


def would_create_open_2x2(
    grid: Grid,
    row: int,
    col: int,
    open_value: int = 0,
) -> bool:
    """Check whether opening one cell would create an HC2 violation.

    This is the cheap local check for a proposal move like wall -> road.
    Only the four 2x2 blocks touching the changed cell can be affected.
    """
    if not grid or not grid[0]:
        return False

    height = len(grid)
    width = len(grid[0])

    if not (0 <= row < height and 0 <= col < width):
        raise IndexError("Cell position is outside the grid.")

    for top_row, left_col in _iter_affected_block_origins(row, col, height, width):
        if _block_is_open_2x2(
            grid,
            top_row,
            left_col,
            open_value,
            override=(row, col),
        ):
            return True

    return False
