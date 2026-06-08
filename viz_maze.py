from collections import deque
from pathlib import Path
import random
import sys

import pygame

import baseline_pipeline as bp
from utils.energy_functions import stamina_aware_baseline_energy_breakdown
from utils.map_analysis import is_walkable, iter_neighbors

MODE = "stamina_only"  # door_only or stamina_only
DISPLAY_STATE = "best"  # final or best
MCMC_STEPS = 1000
RANDOM_SEED = None  # Set to None for a fresh random run each time.
WINDOW_TITLE = "Baseline MCMC Visualizer"
SHOW_SOLUTION_OVERLAY = True

TILE_SIZE = 16
SCALE = 3
TILE_PIXELS = TILE_SIZE * SCALE
ITEM_SIZE = 12
ITEM_PIXELS = ITEM_SIZE * SCALE
OVERLAY_COLORS = (
    (255, 99, 71),
    (255, 191, 0),
    (46, 204, 113),
    (52, 152, 219),
    (155, 89, 182),
    (241, 90, 36),
)

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


def find_semantic_blocked_path(
    state,
    source_position,
    target_position,
    door_is_active,
    collected_item_positions,
):
    semantic_positions = {
        item.position
        for item in state.items
        if item.position not in collected_item_positions
    }

    if door_is_active:
        semantic_positions.add(state.door)

    semantic_positions.discard(source_position)
    semantic_positions.discard(target_position)

    queue = deque([source_position])
    parents = {source_position: None}

    while queue:
        current_position = queue.popleft()

        if current_position == target_position:
            path = [target_position]
            cursor = target_position

            while parents[cursor] is not None:
                cursor = parents[cursor]
                path.append(cursor)

            path.reverse()
            return path

        for next_position in iter_neighbors(*current_position):
            if next_position in parents:
                continue

            if next_position in semantic_positions:
                continue

            if not is_walkable(state.grid, next_position[0], next_position[1]):
                continue

            parents[next_position] = current_position
            queue.append(next_position)

    return []


def get_solution_overlay_paths(state):
    if bp.GAME_MODE != "stamina_only" or not SHOW_SOLUTION_OVERLAY:
        return []

    breakdown = stamina_aware_baseline_energy_breakdown(
        state=state,
        target_path_length=bp.TARGET_PATH_LENGTH,
        target_remaining_stamina=bp.TARGET_FINAL_STAMINA,
    )

    if not breakdown.solution_steps:
        return []

    segment_paths = []
    has_key = False
    collected_item_positions = set()

    for step_index in range(len(breakdown.solution_steps) - 1):
        current_step = breakdown.solution_steps[step_index]
        next_step = breakdown.solution_steps[step_index + 1]
        door_is_active = has_key or not state.locked_door
        path = find_semantic_blocked_path(
            state,
            current_step.position,
            next_step.position,
            door_is_active=door_is_active,
            collected_item_positions=collected_item_positions,
        )

        if path:
            segment_paths.append(path)

        if next_step.kind == "item:key":
            has_key = True
            collected_item_positions.add(next_step.position)
        elif next_step.kind.startswith("item:"):
            collected_item_positions.add(next_step.position)

    return segment_paths


def draw_solution_overlay(screen, state):
    for segment_index, segment_path in enumerate(get_solution_overlay_paths(state)):
        color = OVERLAY_COLORS[segment_index % len(OVERLAY_COLORS)]

        for cell_index in range(len(segment_path) - 1):
            current_row, current_col = segment_path[cell_index]
            next_row, next_col = segment_path[cell_index + 1]
            start_pos = (
                current_col * TILE_PIXELS + TILE_PIXELS // 2,
                current_row * TILE_PIXELS + TILE_PIXELS // 2,
            )
            end_pos = (
                next_col * TILE_PIXELS + TILE_PIXELS // 2,
                next_row * TILE_PIXELS + TILE_PIXELS // 2,
            )
            pygame.draw.line(screen, color, start_pos, end_pos, 6)

        for row_index, col_index in segment_path:
            center = (
                col_index * TILE_PIXELS + TILE_PIXELS // 2,
                row_index * TILE_PIXELS + TILE_PIXELS // 2,
            )
            pygame.draw.circle(screen, color, center, 4)


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

    draw_solution_overlay(screen, state)

    start_row, start_col = state.start
    player_x = start_col * TILE_PIXELS + (TILE_PIXELS - ITEM_PIXELS) // 2
    player_y = start_row * TILE_PIXELS + (TILE_PIXELS - ITEM_PIXELS) // 2
    screen.blit(tiles["player"], (player_x, player_y))


def generate_display_state():
    bp.GAME_MODE = MODE
    bp.MCMC_STEPS = MCMC_STEPS
    effective_seed = RANDOM_SEED if RANDOM_SEED is not None else random.randrange(1, 1_000_000_000)
    bp.RANDOM_SEED = effective_seed
    random.seed(effective_seed)

    final_state, final_energy, best_state, best_energy, _ = bp.run_baseline_mcmc(
        energy_function=bp.get_energy_function(),
    )

    print("\n[Final state]")
    print(bp.render_ascii_map(final_state))
    print(f"Final energy: {final_energy}")
    print(bp.get_energy_breakdown(final_state))
    print(bp.get_solution_summary(final_state, label="final"))
    print(bp.get_agent_difficulty_summary(final_state, label="final"))

    print("\n[Best state visited]")
    print(bp.render_ascii_map(best_state))
    print(f"Best energy: {best_energy}")
    print(bp.get_energy_breakdown(best_state))
    print(bp.get_solution_summary(best_state, label="best"))
    print(bp.get_agent_difficulty_summary(best_state, label="best"))

    if DISPLAY_STATE == "final":
        return final_state, final_energy, "final", effective_seed

    return best_state, best_energy, "best", effective_seed


def main():
    pygame.init()

    state, energy, state_label, effective_seed = generate_display_state()
    width = len(state.grid[0]) * TILE_PIXELS
    height = len(state.grid) * TILE_PIXELS
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(
        f"{WINDOW_TITLE} - mode={MODE} state={state_label} energy={energy} seed={effective_seed}"
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
