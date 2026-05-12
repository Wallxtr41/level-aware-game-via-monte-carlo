from pathlib import Path
import random
import sys

import pygame

import baseline_pipeline as bp

MODE = "stamina_only"
DISPLAY_STATE = "best"  # final or best
MCMC_STEPS = 300
RANDOM_SEED = 20
WINDOW_TITLE = "Baseline MCMC Visualizer"

TILE_SIZE = 16
SCALE = 3
TILE_PIXELS = TILE_SIZE * SCALE
ITEM_SIZE = 12
ITEM_PIXELS = ITEM_SIZE * SCALE

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
    "door_closed": TILES_DIR / "items" / "dumb_closed_door.png",
    "door_open": TILES_DIR / "items" / "dumb_open_door.png",
    "item_stamina": TILES_DIR / "items" / "dumb_stamina.png",
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


def get_tile_surface(tiles, state, row, col):
    if (row, col) == state.door:
        return tiles["door_closed"] if state.locked_door else tiles["door_open"]

    if state.grid[row][col] == 1:
        return tiles["wall"]

    return get_road_tile(tiles, state.grid, row, col)


def get_item_surface(tiles, item_kind):
    return tiles[f"item_{item_kind}"]


def draw_state(screen, tiles, state):
    screen.fill((0, 0, 0))

    for row_index, row in enumerate(state.grid):
        for col_index, _ in enumerate(row):
            x = col_index * TILE_PIXELS
            y = row_index * TILE_PIXELS
            tile_surface = get_tile_surface(tiles, state, row_index, col_index)
            screen.blit(tile_surface, (x, y))

    for item in state.items:
        row_index, col_index = item.position
        x = col_index * TILE_PIXELS
        y = row_index * TILE_PIXELS
        item_surface = get_item_surface(tiles, item.kind)
        item_x = x + (TILE_PIXELS - ITEM_PIXELS) // 2
        item_y = y + (TILE_PIXELS - ITEM_PIXELS) // 2
        screen.blit(item_surface, (item_x, item_y))

    start_row, start_col = state.start
    player_x = start_col * TILE_PIXELS + (TILE_PIXELS - ITEM_PIXELS) // 2
    player_y = start_row * TILE_PIXELS + (TILE_PIXELS - ITEM_PIXELS) // 2
    screen.blit(tiles["player"], (player_x, player_y))


def generate_display_state():
    bp.GAME_MODE = MODE
    bp.MCMC_STEPS = MCMC_STEPS
    bp.RANDOM_SEED = RANDOM_SEED

    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)

    final_state, final_energy, best_state, best_energy, _ = bp.run_baseline_mcmc(
        energy_function=bp.ENERGY_FUNCTION,
    )

    if DISPLAY_STATE == "final":
        return final_state, final_energy, "final"

    return best_state, best_energy, "best"


def main():
    pygame.init()

    state, energy, state_label = generate_display_state()
    width = len(state.grid[0]) * TILE_PIXELS
    height = len(state.grid) * TILE_PIXELS
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(
        f"{WINDOW_TITLE} - mode={MODE} state={state_label} energy={energy}"
    )

    tiles = load_tiles()
    clock = pygame.time.Clock()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        draw_state(screen, tiles, state)
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
