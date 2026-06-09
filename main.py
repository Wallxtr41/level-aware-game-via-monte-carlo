from pathlib import Path
import sys

import pygame

from utils.maze_generation import MAP_HEIGHT, MAP_WIDTH
from utils.map_entities import MazeLayout, generate_maze_layout

TILE_SIZE = 16
SCALE = 3
TILE_PIXELS = TILE_SIZE * SCALE
ITEM_SIZE = 12
ITEM_PIXELS = ITEM_SIZE * SCALE

BASE_DIR = Path(__file__).resolve().parent
TILES_DIR = BASE_DIR / "tiles"
ROAD_TILE_PATH = TILES_DIR / "default_road" / "road.png"

TILE_PATHS = {
    "wall": TILES_DIR / "wall" / "wall.png",
    "road": ROAD_TILE_PATH,
    "door_closed": TILES_DIR / "items" / "dumb_closed_door.png",
    "door_open": TILES_DIR / "items" / "dumb_open_door.png",
    "item_stamina": TILES_DIR / "items" / "dumb_stamina.png",
    "item_power": TILES_DIR / "items" / "dumb_power.png",
    "item_key": TILES_DIR / "items" / "dumb_key.png",
    "player": TILES_DIR / "player" / "dumb_player.png",
}


def load_tile(path, size):
    image = pygame.image.load(path).convert_alpha()
    return pygame.transform.scale(image, size)


def load_tiles():
    tiles = {}

    for name, path in TILE_PATHS.items():
        if name.startswith("item_"):
            size = (ITEM_PIXELS, ITEM_PIXELS)
        else:
            size = (TILE_PIXELS, TILE_PIXELS)

        tiles[name] = load_tile(path, size)

    return tiles


def is_road(map_data, row, col):
    if row < 0 or row >= len(map_data):
        return False
    if col < 0 or col >= len(map_data[0]):
        return False
    return map_data[row][col] == 0


def get_road_tile(tiles, map_data, row, col):
    return tiles["road"]


def get_tile_surface(tiles, map_data, row, col, door_position):
    if (row, col) == door_position:
        return tiles["door_closed"]

    if map_data[row][col] == 1:
        return tiles["wall"]

    return get_road_tile(tiles, map_data, row, col)


def get_item_surface(tiles, item_kind):
    return tiles[f"item_{item_kind}"]


def draw_map(screen, tiles, layout: MazeLayout):
    screen.fill((0, 0, 0))

    for row_index, row in enumerate(layout.grid):
        for col_index, _ in enumerate(row):
            x = col_index * TILE_PIXELS
            y = row_index * TILE_PIXELS
            tile_surface = get_tile_surface(
                tiles,
                layout.grid,
                row_index,
                col_index,
                layout.door,
            )
            screen.blit(tile_surface, (x, y))

    for item in layout.items:
        row_index, col_index = item.position
        x = col_index * TILE_PIXELS
        y = row_index * TILE_PIXELS
        item_surface = get_item_surface(tiles, item.kind)
        item_x = x + (TILE_PIXELS - ITEM_PIXELS) // 2
        item_y = y + (TILE_PIXELS - ITEM_PIXELS) // 2
        screen.blit(item_surface, (item_x, item_y))

    start_row, start_col = layout.start
    player_x = start_col * TILE_PIXELS + (TILE_PIXELS - ITEM_PIXELS) // 2
    player_y = start_row * TILE_PIXELS + (TILE_PIXELS - ITEM_PIXELS) // 2
    screen.blit(tiles["player"], (player_x, player_y))


def main():
    pygame.init()

    current_layout = generate_maze_layout(MAP_WIDTH, MAP_HEIGHT)

    width = len(current_layout.grid[0]) * TILE_PIXELS
    height = len(current_layout.grid) * TILE_PIXELS

    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Maze Map Test - R: Yeni Harita")

    tiles = load_tiles()
    clock = pygame.time.Clock()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                current_layout = generate_maze_layout(MAP_WIDTH, MAP_HEIGHT)

        draw_map(screen, tiles, current_layout)

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
