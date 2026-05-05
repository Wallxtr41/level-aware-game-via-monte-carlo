from pathlib import Path
import sys

import pygame

from utils.maze_generation import MAP_HEIGHT, MAP_WIDTH, generate_maze_map

TILE_SIZE = 16
SCALE = 3
TILE_PIXELS = TILE_SIZE * SCALE

BASE_DIR = Path(__file__).resolve().parent
TILES_DIR = BASE_DIR / "tiles"

TILE_PATHS = {
    "wall": TILES_DIR / "wall" / "wall.png",
    "road_two_edge_up_down": TILES_DIR / "road_two_edge" / "road_two_edge_up_down.png",
    "road_two_edge_right_left": TILES_DIR / "road_two_edge" / "road_two_edge_right_left.png",
    "road_one_corner_northeast": TILES_DIR / "road_one_corner" / "road_one_corner_northeast.png",
    "road_one_corner_southeast": TILES_DIR / "road_one_corner" / "road_one_corner_southeast.png",
    "road_one_corner_southwest": TILES_DIR / "road_one_corner" / "road_one_corner_southwest.png",
    "road_one_corner_northwest": TILES_DIR / "road_one_corner" / "road_one_corner_northwest.png",
    "road_two_corner_up": TILES_DIR / "road_two_corner" / "road_two_corner_up.png",
    "road_two_corner_right": TILES_DIR / "road_two_corner" / "road_two_corner_right.png",
    "road_two_corner_down": TILES_DIR / "road_two_corner" / "road_two_corner_down.png",
    "road_two_corner_left": TILES_DIR / "road_two_corner" / "road_two_corner_left.png",
    "threeway_up": TILES_DIR / "threeway" / "threeway_up.png",
    "threeway_right": TILES_DIR / "threeway" / "threeway_right.png",
    "threeway_down": TILES_DIR / "threeway" / "threeway_down.png",
    "threeway_left": TILES_DIR / "threeway" / "threeway_left.png",
    "crossroads": TILES_DIR / "crossroads" / "crossroads.png",
}


def load_tile(path):
    image = pygame.image.load(path).convert_alpha()
    return pygame.transform.scale(image, (TILE_PIXELS, TILE_PIXELS))


def load_tiles():
    return {name: load_tile(path) for name, path in TILE_PATHS.items()}


def is_road(map_data, row, col):
    if row < 0 or row >= len(map_data):
        return False
    if col < 0 or col >= len(map_data[0]):
        return False
    return map_data[row][col] == 0


def get_road_tile(tiles, map_data, row, col):
    up = is_road(map_data, row - 1, col)
    right = is_road(map_data, row, col + 1)
    down = is_road(map_data, row + 1, col)
    left = is_road(map_data, row, col - 1)

    road_count = up + right + down + left

    if road_count == 1:
        if up:
            return tiles["road_two_corner_down"]
        if right:
            return tiles["road_two_corner_left"]
        if down:
            return tiles["road_two_corner_up"]
        return tiles["road_two_corner_right"]

    if road_count == 2:
        if up and down:
            return tiles["road_two_edge_up_down"]
        if left and right:
            return tiles["road_two_edge_right_left"]
        if up and right:
            return tiles["road_one_corner_southwest"]
        if right and down:
            return tiles["road_one_corner_northwest"]
        if down and left:
            return tiles["road_one_corner_northeast"]
        return tiles["road_one_corner_southeast"]

    if road_count == 3:
        if not up:
            return tiles["threeway_up"]
        if not right:
            return tiles["threeway_right"]
        if not down:
            return tiles["threeway_down"]
        return tiles["threeway_left"]

    if road_count == 4:
        return tiles["crossroads"]

    return tiles["road_two_corner_up"]


def get_tile_surface(tiles, map_data, row, col):
    if map_data[row][col] == 1:
        return tiles["wall"]
    return get_road_tile(tiles, map_data, row, col)


def draw_map(screen, tiles, map_data):
    screen.fill((0, 0, 0))

    for row_index, row in enumerate(map_data):
        for col_index, _ in enumerate(row):
            x = col_index * TILE_PIXELS
            y = row_index * TILE_PIXELS
            tile_surface = get_tile_surface(tiles, map_data, row_index, col_index)
            screen.blit(tile_surface, (x, y))


def main():
    pygame.init()

    current_map = generate_maze_map(MAP_WIDTH, MAP_HEIGHT)

    width = len(current_map[0]) * TILE_PIXELS
    height = len(current_map) * TILE_PIXELS

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
                current_map = generate_maze_map(MAP_WIDTH, MAP_HEIGHT)

        draw_map(screen, tiles, current_map)

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
