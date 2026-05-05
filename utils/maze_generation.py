from __future__ import annotations

import random

MAP_WIDTH = 21
MAP_HEIGHT = 15
EXTRA_CONNECTION_CHANCE = 0.12


def clamp_to_odd(value: int) -> int:
    return value if value % 2 == 1 else value + 1


def creates_open_square(map_data: list[list[int]], row: int, col: int) -> bool:
    for row_offset in (-1, 0):
        for col_offset in (-1, 0):
            cells = []

            for current_row in (row + row_offset, row + row_offset + 1):
                for current_col in (col + col_offset, col + col_offset + 1):
                    if 0 <= current_row < len(map_data) and 0 <= current_col < len(map_data[0]):
                        if current_row == row and current_col == col:
                            cells.append(0)
                        else:
                            cells.append(map_data[current_row][current_col])

            if len(cells) == 4 and all(cell == 0 for cell in cells):
                return True

    return False


def carve_extra_connections(map_data: list[list[int]], chance: float) -> None:
    candidates = []

    for row in range(1, len(map_data) - 1):
        for col in range(1, len(map_data[0]) - 1):
            if map_data[row][col] == 0:
                continue

            road_neighbors = sum((
                map_data[row - 1][col] == 0,
                map_data[row][col + 1] == 0,
                map_data[row + 1][col] == 0,
                map_data[row][col - 1] == 0,
            ))

            if road_neighbors >= 2:
                candidates.append((row, col))

    random.shuffle(candidates)

    for row, col in candidates:
        if random.random() >= chance:
            continue

        if creates_open_square(map_data, row, col):
            continue

        map_data[row][col] = 0


def generate_maze_map(
    width: int,
    height: int,
    extra_connection_chance: float = EXTRA_CONNECTION_CHANCE,
) -> list[list[int]]:
    width = max(5, clamp_to_odd(width))
    height = max(5, clamp_to_odd(height))

    map_data = [[1 for _ in range(width)] for _ in range(height)]
    map_data[1][1] = 0
    stack = [(1, 1)]
    directions = [(0, -2), (2, 0), (0, 2), (-2, 0)]

    while stack:
        col, row = stack[-1]
        neighbors = []

        for dx, dy in directions:
            next_col = col + dx
            next_row = row + dy

            if 1 <= next_col < width - 1 and 1 <= next_row < height - 1:
                if map_data[next_row][next_col] == 1:
                    neighbors.append((next_col, next_row, dx, dy))

        if not neighbors:
            stack.pop()
            continue

        next_col, next_row, dx, dy = random.choice(neighbors)
        wall_col = col + (dx // 2)
        wall_row = row + (dy // 2)

        map_data[wall_row][wall_col] = 0
        map_data[next_row][next_col] = 0
        stack.append((next_col, next_row))

    carve_extra_connections(map_data, extra_connection_chance)

    return map_data
