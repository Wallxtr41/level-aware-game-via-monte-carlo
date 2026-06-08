"""
play_maze.py  --  Monte Carlo ile uretilen labirentte oynanabilir mod
WASD / Ok tuslari: Hareket   R: Yeni labirent   Q / ESC: Cikis
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
import random
import sys

import pygame

import baseline_pipeline as bp
from utils.energy_functions import stamina_aware_baseline_energy_breakdown
from utils.map_analysis import is_walkable, iter_neighbors

# ── Ayarlar ─────────────────────────────────────────────────────────────────────
TILE_SIZE = 16
SCALE = 3
TILE_PIXELS = TILE_SIZE * SCALE
ITEM_SIZE = 12
ITEM_PIXELS = ITEM_SIZE * SCALE

HUD_HEIGHT = 72
FOG_RADIUS = 1
MCMC_STEPS = 500
REPLAY_FRAMES_PER_STEP = 6   # replay hizi: her N frame'de 1 adim

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

COLOR_BG = (15, 15, 25)
COLOR_HUD_BG = (20, 20, 35)
COLOR_STAMINA_FULL = (46, 204, 113)
COLOR_STAMINA_LOW = (231, 76, 60)
COLOR_STAMINA_EMPTY = (60, 20, 20)
COLOR_TEXT = (220, 220, 220)
COLOR_KEY_ACTIVE = (255, 215, 0)
COLOR_KEY_INACTIVE = (70, 70, 70)
COLOR_WIN = (46, 204, 113)
COLOR_LOSE = (231, 76, 60)
COLOR_HINT = (90, 90, 120)


# ── Veri yapilari ────────────────────────────────────────────────────────────────

@dataclass
class GameState:
    mc_state: bp.BaselineState
    player_pos: tuple
    stamina: int
    max_stamina: int
    has_key: bool
    door_open: bool
    collected_items: set
    visible_cells: set
    seen_cells: set
    status: str                 # "playing" | "won" | "lost"
    message: str = ""
    replay_path: list = field(default_factory=list)   # duz path (animasyon icin)
    replay_frame: int = 0


# ── Tile yukleme ─────────────────────────────────────────────────────────────────

def load_tile(path, size):
    image = pygame.image.load(path).convert_alpha()
    return pygame.transform.scale(image, size)


def load_tiles():
    tiles = {}
    for name, path in TILE_PATHS.items():
        size = (ITEM_PIXELS, ITEM_PIXELS) if name.startswith("item_") else (TILE_PIXELS, TILE_PIXELS)
        tiles[name] = load_tile(path, size)
    return tiles


# ── Yol tile secimi ──────────────────────────────────────────────────────────────

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
        if up:    return tiles["road_two_corner_down"]
        if right: return tiles["road_two_corner_left"]
        if down:  return tiles["road_two_corner_up"]
        return tiles["road_two_corner_right"]
    if road_count == 2:
        if up and down:    return tiles["road_two_edge_up_down"]
        if left and right: return tiles["road_two_edge_right_left"]
        if up and right:   return tiles["road_one_corner_southwest"]
        if right and down: return tiles["road_one_corner_northwest"]
        if down and left:  return tiles["road_one_corner_northeast"]
        return tiles["road_one_corner_southeast"]
    if road_count == 3:
        if not up:    return tiles["threeway_up"]
        if not right: return tiles["threeway_right"]
        if not down:  return tiles["threeway_down"]
        return tiles["threeway_left"]
    if road_count == 4:
        return tiles["crossroads"]
    return tiles["road_two_corner_up"]


# ── Fog of war ───────────────────────────────────────────────────────────────────

def compute_visible_cells(grid, center, radius):
    queue = deque([(center, 0)])
    visited = {center: 0}
    visible = {center}

    while queue:
        (row, col), dist = queue.popleft()
        if dist >= radius:
            continue
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nb = (row + dr, col + dc)
            if nb in visited:
                continue
            nr, nc = nb
            if nr < 0 or nr >= len(grid) or nc < 0 or nc >= len(grid[0]):
                continue
            visited[nb] = dist + 1
            visible.add(nb)
            queue.append((nb, dist + 1))

    return visible


# ── Cozum yolu hesaplama (replay icin) ───────────────────────────────────────────

def find_semantic_blocked_path(
    state,
    source_pos,
    target_pos,
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
    semantic_positions.discard(source_pos)
    semantic_positions.discard(target_pos)

    queue = deque([source_pos])
    parents = {source_pos: None}

    while queue:
        current = queue.popleft()
        if current == target_pos:
            path = [target_pos]
            cursor = target_pos
            while parents[cursor] is not None:
                cursor = parents[cursor]
                path.append(cursor)
            path.reverse()
            return path

        for nb in iter_neighbors(*current):
            if nb in parents:
                continue
            if nb in semantic_positions:
                continue
            if not is_walkable(state.grid, nb[0], nb[1]):
                continue
            parents[nb] = current
            queue.append(nb)

    return []


def compute_replay_path(mc_state):
    """MC state'in optimal cozum pathini duz liste olarak dondurur."""
    breakdown = stamina_aware_baseline_energy_breakdown(
        state=mc_state,
        target_path_length=bp.TARGET_PATH_LENGTH,
        target_remaining_stamina=bp.TARGET_FINAL_STAMINA,
    )
    if not breakdown.solution_steps:
        return []

    segments = []
    has_key = False
    collected_item_positions = set()

    for i in range(len(breakdown.solution_steps) - 1):
        curr = breakdown.solution_steps[i]
        nxt = breakdown.solution_steps[i + 1]
        path = find_semantic_blocked_path(
            mc_state, curr.position, nxt.position,
            door_is_active=(has_key or not mc_state.locked_door),
            collected_item_positions=collected_item_positions,
        )
        if path:
            segments.append(path)
        if nxt.kind == "item:key":
            has_key = True
            collected_item_positions.add(nxt.position)
        elif nxt.kind.startswith("item:"):
            collected_item_positions.add(nxt.position)

    flat: list = []
    for seg in segments:
        if flat and flat[-1] == seg[0]:
            flat.extend(seg[1:])
        else:
            flat.extend(seg)

    return flat


# ── Labirent uretimi ─────────────────────────────────────────────────────────────

def generate_game_state():
    bp.GAME_MODE = "stamina_only"
    bp.MCMC_STEPS = MCMC_STEPS
    seed = random.randrange(1, 1_000_000_000)
    bp.RANDOM_SEED = seed
    random.seed(seed)

    print(f"\n[play_maze] Monte Carlo labirent uretiliyor... (seed={seed})")
    _, _, best_state, best_energy, _ = bp.run_baseline_mcmc(
        energy_function=bp.get_energy_function(),
    )
    print(f"[play_maze] Labirent hazir. Enerji={best_energy:.2f}")
    print("\n[play_maze] Best state visited")
    print(bp.render_ascii_map(best_state))
    print(f"Best energy: {best_energy}")
    print(bp.get_energy_breakdown(best_state))
    print(bp.get_solution_summary(best_state, label="best"))
    print(bp.get_agent_difficulty_summary(best_state, label="best"))
    print(f"Best door position: {best_state.door}")
    print(f"Best locked door: {best_state.locked_door}")
    print(f"Best initial stamina: {best_state.initial_stamina}")
    print(f"Best items: {[(item.kind, item.position, item.value) for item in best_state.items]}")

    player_pos = best_state.start
    visible = compute_visible_cells(best_state.grid, player_pos, FOG_RADIUS)

    return GameState(
        mc_state=best_state,
        player_pos=player_pos,
        stamina=best_state.initial_stamina,
        max_stamina=best_state.initial_stamina,
        has_key=False,
        door_open=not best_state.locked_door,
        collected_items=set(),
        visible_cells=visible,
        seen_cells=set(visible),
        status="playing",
    )


# ── Oyun mekanigi ────────────────────────────────────────────────────────────────

def try_move(game, dr, dc):
    if game.status != "playing":
        return None

    row, col = game.player_pos
    nr, nc = row + dr, col + dc
    grid = game.mc_state.grid

    if nr < 0 or nr >= len(grid) or nc < 0 or nc >= len(grid[0]):
        return None
    if grid[nr][nc] == 1:
        return None

    target = (nr, nc)
    door = game.mc_state.door

    new_stamina = game.stamina - 1
    new_has_key = game.has_key
    new_door_open = game.door_open
    new_collected = set(game.collected_items)
    new_status = "playing"
    new_message = ""
    new_replay_path = []

    # Item toplama
    for idx, item in enumerate(game.mc_state.items):
        if item.position == target and idx not in new_collected:
            new_collected.add(idx)
            if item.kind == "stamina":
                new_stamina += item.value
            elif item.kind == "key":
                new_has_key = True

    # Kapiya basmak: anahtar varsa kapi acilir ve kazanilir;
    # anahtar yoksa sadece uzerinden gecer, engellenmez.
    if target == door:
        if not new_door_open and new_has_key:
            new_door_open = True
        if new_door_open:
            new_status = "won"
            new_message = "Kactin! Tebrikler!  [R: Yeni oyun]"

    # Stamina tukendi
    if new_stamina <= 0 and new_status == "playing":
        new_stamina = 0
        new_status = "lost"
        new_message = "Stamina bitti!  [R: Yeni oyun]"
        new_replay_path = compute_replay_path(game.mc_state)

    new_visible = compute_visible_cells(grid, target, FOG_RADIUS)
    new_seen = game.seen_cells | new_visible

    return GameState(
        mc_state=game.mc_state,
        player_pos=target,
        stamina=new_stamina,
        max_stamina=game.max_stamina,
        has_key=new_has_key,
        door_open=new_door_open,
        collected_items=new_collected,
        visible_cells=new_visible,
        seen_cells=new_seen,
        status=new_status,
        message=new_message,
        replay_path=new_replay_path,
        replay_frame=0,
    )


# ── Cizim ────────────────────────────────────────────────────────────────────────

def draw_map(screen, tiles, game, replay_player_pos=None, replay_collected=None, replay_door_open=None):
    """
    Haritayi ciz.
    - replay_player_pos: replay modunda karakterin animasyon konumu
    - replay_collected:  replay modunda o ana kadar toplanmis item seti
    - replay_door_open:  replay modunda kapinin acik/kapali durumu
    status=="lost" ise fog kalkar ve tum harita gosterilir.
    """
    grid = game.mc_state.grid
    reveal_all = (game.status == "lost")
    screen.fill(COLOR_BG)

    for row_index, row in enumerate(grid):
        for col_index in range(len(row)):
            cell = (row_index, col_index)
            x = col_index * TILE_PIXELS
            y = row_index * TILE_PIXELS

            if not reveal_all and cell not in game.seen_cells:
                pygame.draw.rect(screen, (0, 0, 0), (x, y, TILE_PIXELS, TILE_PIXELS))
                continue

            if cell == game.mc_state.door:
                if replay_door_open is not None:
                    is_open = replay_door_open
                else:
                    # Anahtar alindiginda kapi gorsel olarak "acik" duruma gecer
                    is_open = game.door_open or game.has_key
                tile = tiles["door_open"] if is_open else tiles["door_closed"]
            elif grid[row_index][col_index] == 1:
                tile = tiles["wall"]
            else:
                tile = get_road_tile(tiles, grid, row_index, col_index)

            screen.blit(tile, (x, y))

            if not reveal_all and cell not in game.visible_cells:
                dark = pygame.Surface((TILE_PIXELS, TILE_PIXELS), pygame.SRCALPHA)
                dark.fill((0, 0, 0, 150))
                screen.blit(dark, (x, y))

    # Item'lar: replay modunda o ana kadar toplanmislari gizle
    effective_collected = replay_collected if replay_collected is not None else game.collected_items
    for idx, item in enumerate(game.mc_state.items):
        if idx in effective_collected:
            continue
        if not reveal_all and item.position not in game.visible_cells:
            continue
        r, c = item.position
        x = c * TILE_PIXELS + (TILE_PIXELS - ITEM_PIXELS) // 2
        y = r * TILE_PIXELS + (TILE_PIXELS - ITEM_PIXELS) // 2
        screen.blit(tiles[f"item_{item.kind}"], (x, y))

    # Oyuncu
    pr, pc = replay_player_pos if replay_player_pos is not None else game.player_pos
    px = pc * TILE_PIXELS + (TILE_PIXELS - ITEM_PIXELS) // 2
    py = pr * TILE_PIXELS + (TILE_PIXELS - ITEM_PIXELS) // 2
    screen.blit(tiles["player"], (px, py))


def draw_hud(screen, font, game, map_height_px):
    hud_top = map_height_px
    total_w = screen.get_width()

    pygame.draw.rect(screen, COLOR_HUD_BG, (0, hud_top, total_w, HUD_HEIGHT))
    pygame.draw.line(screen, (50, 50, 80), (0, hud_top), (total_w, hud_top), 2)

    bar_margin = 12
    bar_x = bar_margin
    bar_y = hud_top + 10
    bar_w = total_w - 2 * bar_margin
    bar_h = 20

    ratio = game.stamina / game.max_stamina if game.max_stamina > 0 else 0
    fill_color = COLOR_STAMINA_FULL if ratio > 0.35 else COLOR_STAMINA_LOW

    pygame.draw.rect(screen, COLOR_STAMINA_EMPTY, (bar_x, bar_y, bar_w, bar_h))
    if ratio > 0:
        pygame.draw.rect(screen, fill_color, (bar_x, bar_y, int(bar_w * ratio), bar_h))
    pygame.draw.rect(screen, (90, 90, 120), (bar_x, bar_y, bar_w, bar_h), 1)

    stamina_label = f"STAMINA  {game.stamina} / {game.max_stamina}"
    screen.blit(font.render(stamina_label, True, COLOR_TEXT), (bar_x + 6, bar_y + 3))

    second_row_y = hud_top + 40

    if game.status == "lost":
        hint_text = "Optimal cozum gosteriliyor...   R: Yeni oyun   Q/ESC: Cikis"
        hint_surf = font.render(hint_text, True, (160, 120, 60))
        screen.blit(hint_surf, (total_w - hint_surf.get_width() - bar_margin, second_row_y))
    else:
        key_color = COLOR_KEY_ACTIVE if game.has_key else COLOR_KEY_INACTIVE
        key_label = "ANAHTAR: VAR  [kapi acilabilir]" if game.has_key else "ANAHTAR: YOK"
        screen.blit(font.render(key_label, True, key_color), (bar_x, second_row_y))
        hint_surf = font.render("WASD/Ok: Hareket   R: Yeni   Q/ESC: Cikis", True, COLOR_HINT)
        screen.blit(hint_surf, (total_w - hint_surf.get_width() - bar_margin, second_row_y))

    if game.message:
        msg_color = COLOR_WIN if game.status == "won" else COLOR_LOSE
        msg_surf = font.render(game.message, True, msg_color)
        mx = total_w // 2 - msg_surf.get_width() // 2
        screen.blit(msg_surf, (mx, bar_y + 2))


# ── Ana dongu ─────────────────────────────────────────────────────────────────────

def main():
    pygame.init()

    game = generate_game_state()

    grid = game.mc_state.grid
    map_w = len(grid[0]) * TILE_PIXELS
    map_h = len(grid) * TILE_PIXELS
    total_h = map_h + HUD_HEIGHT

    screen = pygame.display.set_mode((map_w, total_h))
    pygame.display.set_caption("MC Maze -- Oynanabilir Mod")

    tiles = load_tiles()
    font = pygame.font.SysFont("consolas", 14, bold=True)
    clock = pygame.time.Clock()

    # Item konumundan index'e hizli erisim icin onceden hesapla (replay'de kullanilir)
    item_pos_map: dict = {}

    regenerating = False

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    pygame.quit()
                    sys.exit()

                if event.key == pygame.K_r:
                    regenerating = True

                if not regenerating and game.status == "playing":
                    move = None
                    if event.key in (pygame.K_UP, pygame.K_w):
                        move = (-1, 0)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        move = (1, 0)
                    elif event.key in (pygame.K_LEFT, pygame.K_a):
                        move = (0, -1)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        move = (0, 1)

                    if move is not None:
                        result = try_move(game, *move)
                        if result is not None:
                            game = result
                            item_pos_map = {}  # yeni state icin temizle

        if regenerating:
            draw_map(screen, tiles, game)
            draw_hud(screen, font, game, map_h)
            loading_font = pygame.font.SysFont("consolas", 18, bold=True)
            msg = loading_font.render("Yeni labirent uretiliyor...", True, (200, 200, 60))
            overlay = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))
            screen.blit(msg, (map_w // 2 - msg.get_width() // 2, map_h // 2 - msg.get_height() // 2))
            pygame.display.flip()

            game = generate_game_state()
            item_pos_map = {}
            regenerating = False
            continue

        # ── Replay animasyonu ────────────────────────────────────────────────────
        replay_pos = None
        replay_collected = None
        replay_door_open = None

        if game.status == "lost" and game.replay_path:
            # item_pos_map'i bir kez olustur
            if not item_pos_map:
                item_pos_map = {item.position: idx for idx, item in enumerate(game.mc_state.items)}

            step = (game.replay_frame // REPLAY_FRAMES_PER_STEP) % len(game.replay_path)
            replay_pos = game.replay_path[step]

            # O adima kadar hangi itemler "toplandi"
            replay_collected = set()
            for i in range(step + 1):
                pos = game.replay_path[i]
                if pos in item_pos_map:
                    replay_collected.add(item_pos_map[pos])

            # Anahtar toplandi mi? Toplandi ise kapi gorsel olarak hemen acikilir
            replay_has_key = any(
                game.mc_state.items[idx].kind == "key" for idx in replay_collected
            )
            replay_door_open = replay_has_key

            game.replay_frame += 1

        draw_map(screen, tiles, game,
                 replay_player_pos=replay_pos,
                 replay_collected=replay_collected,
                 replay_door_open=replay_door_open)
        draw_hud(screen, font, game, map_h)
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
