from __future__ import annotations

import random

from utils.hard_constraints import (
    can_open_cell_preserve_connectivity,
    can_remove_cell_preserve_connectivity,
    find_open_2x2_blocks,
    get_reachable_walkable_count,
    is_hc1_satisfied,
    is_hc2_satisfied,
    would_create_open_2x2,
)
from utils.maze_generation import MAP_HEIGHT, MAP_WIDTH, generate_maze_map


TEST_MODE = "maze"  # random or maze
TEST_WIDTH = MAP_WIDTH
TEST_HEIGHT = MAP_HEIGHT
WALL_PROBABILITY = 0.35
RANDOM_SEED = 42
START_ROW = 1
START_COL = 1


def generate_random_grid(width: int, height: int, wall_probability: float) -> list[list[int]]:
    return [
        [1 if random.random() < wall_probability else 0 for _ in range(width)]
        for _ in range(height)
    ]


def print_grid(grid: list[list[int]]) -> None:
    for row in grid:
        print(" ".join("." if cell == 0 else "#" for cell in row))


def run_hc2_report(grid: list[list[int]], label: str) -> None:
    violations = find_open_2x2_blocks(grid)

    print(f"\n[{label}]")
    print_grid(grid)
    print(f"HC2 satisfied: {is_hc2_satisfied(grid)}")
    print(f"Open 2x2 blocks: {violations}")


def run_local_move_demo(grid: list[list[int]]) -> None:
    print("\n[Local proposal check: wall -> road]")

    wall_cells = [
        (row_index, col_index)
        for row_index, row in enumerate(grid)
        for col_index, cell in enumerate(row)
        if cell == 1
    ]

    if not wall_cells:
        print("No wall cell found for local HC2 proposal test.")
        return

    row, col = random.choice(wall_cells)
    creates_violation = would_create_open_2x2(grid, row, col)

    print(f"Selected wall cell: ({row}, {col})")
    print(f"Would opening this cell violate HC2? {creates_violation}")


def run_hc1_report(grid: list[list[int]]) -> None:
    print("\n[HC1 connectivity check]")

    reachable = get_reachable_walkable_count(grid, START_ROW, START_COL)
    total_walkable = sum(cell == 0 for row in grid for cell in row)

    print(f"Start cell: ({START_ROW}, {START_COL})")
    print(f"Reachable walkable cells: {reachable}")
    print(f"Total walkable cells: {total_walkable}")
    print(f"HC1 satisfied: {is_hc1_satisfied(grid, START_ROW, START_COL)}")


def run_hc1_local_move_demo(grid: list[list[int]]) -> None:
    print("\n[Local proposal check: HC1]")

    wall_cells = [
        (row_index, col_index)
        for row_index, row in enumerate(grid)
        for col_index, cell in enumerate(row)
        if cell == 1
    ]
    road_cells = [
        (row_index, col_index)
        for row_index, row in enumerate(grid)
        for col_index, cell in enumerate(row)
        if cell == 0
    ]

    if wall_cells:
        open_row, open_col = random.choice(wall_cells)
        print(f"Selected wall cell for opening: ({open_row}, {open_col})")
        print(
            "Opening locally preserves connectivity? "
            f"{can_open_cell_preserve_connectivity(grid, open_row, open_col)}"
        )

    if road_cells:
        close_row, close_col = random.choice(road_cells)
        print(f"Selected road cell for closing: ({close_row}, {close_col})")
        print(
            "Closing is guaranteed safe locally? "
            f"{can_remove_cell_preserve_connectivity(grid, close_row, close_col)}"
        )


def main() -> None:
    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)

    if TEST_MODE == "maze":
        grid = generate_maze_map(TEST_WIDTH, TEST_HEIGHT)
        label = f"maze {len(grid[0])}x{len(grid)}"
    else:
        grid = generate_random_grid(TEST_WIDTH, TEST_HEIGHT, WALL_PROBABILITY)
        label = f"random {TEST_WIDTH}x{TEST_HEIGHT}"

    run_hc2_report(grid, label)
    run_local_move_demo(grid)
    run_hc1_report(grid)
    run_hc1_local_move_demo(grid)


if __name__ == "__main__":
    main()
