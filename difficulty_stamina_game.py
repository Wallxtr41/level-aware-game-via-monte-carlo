from __future__ import annotations

from dataclasses import dataclass
import random
import sys

import pygame

import baseline_pipeline as bp
import play_maze as pm
from utils import game_config


MENU_SIZE = (980, 720)
CUSTOM_MCMC_STEPS = 700
LEVEL_MCMC_STEPS = 700
RANDOM_SEED_SENTINEL = 0
PREFERRED_PLAY_SCALE = 4
MIN_PLAY_SCALE = 2
MAX_PLAY_WINDOW_SIZE = (1400, 920)


@dataclass(frozen=True)
class LevelPreset:
    name: str
    config: game_config.DifficultyStaminaConfig
    seed: int
    mcmc_steps: int = LEVEL_MCMC_STEPS


@dataclass
class PlaySession:
    game: pm.GameState
    settings: game_config.DifficultyStaminaConfig
    seed: int
    mcmc_steps: int
    mode: str
    level_index: int | None = None
    item_pos_map: dict[tuple[int, int], int] | None = None


@dataclass
class InputField:
    key: str
    label: str
    value: str
    hint: str


LEVELS: tuple[LevelPreset, ...] = (
    LevelPreset("01 - Warmup", game_config.DifficultyStaminaConfig(0.05, 1, 11, 11, False, 0, 8), 11001, 400),
    LevelPreset("02 - First Key", game_config.DifficultyStaminaConfig(0.10, 1, 11, 11, True, 0, 8), 11002, 450),
    LevelPreset("03 - Small Fog", game_config.DifficultyStaminaConfig(0.15, 1, 13, 11, True, 0, 10), 11003, 500),
    LevelPreset("04 - First Stamina", game_config.DifficultyStaminaConfig(0.20, 1, 13, 13, True, 1, 10), 11004, 550),
    LevelPreset("05 - Longer Route", game_config.DifficultyStaminaConfig(0.25, 1, 15, 13, True, 1, 12), 11005, 600),
    LevelPreset("06 - Low Vision", game_config.DifficultyStaminaConfig(0.30, 1, 15, 13, True, 1, 12), 11006, 650),
    LevelPreset("07 - Branches", game_config.DifficultyStaminaConfig(0.35, 1, 15, 15, True, 1, 12), 11007, 700),
    LevelPreset("08 - Double Stamina", game_config.DifficultyStaminaConfig(0.40, 1, 17, 15, True, 2, 12), 11008, 750),
    LevelPreset("09 - Tight Vision", game_config.DifficultyStaminaConfig(0.45, 1, 17, 15, True, 2, 12), 11009, 800),
    LevelPreset("10 - Midpoint", game_config.DifficultyStaminaConfig(0.50, 1, 17, 17, True, 2, 15), 11010, 850),
    LevelPreset("11 - Wider Maze", game_config.DifficultyStaminaConfig(0.55, 1, 19, 17, True, 2, 15), 11011, 900),
    LevelPreset("12 - Stamina Chain", game_config.DifficultyStaminaConfig(0.60, 1, 19, 17, True, 3, 15), 11012, 950),
    LevelPreset("13 - Bigger Map", game_config.DifficultyStaminaConfig(0.62, 1, 19, 19, True, 3, 15), 11013, 1000),
    LevelPreset("14 - Longer Corridors", game_config.DifficultyStaminaConfig(0.65, 1, 21, 19, True, 3, 15), 11014, 1050),
    LevelPreset("15 - Hard Turns", game_config.DifficultyStaminaConfig(0.68, 1, 21, 21, True, 3, 15), 11015, 1100),
    LevelPreset("16 - Wide Hard", game_config.DifficultyStaminaConfig(0.72, 1, 23, 21, True, 3, 18), 11016, 1150),
    LevelPreset("17 - Larger Hard", game_config.DifficultyStaminaConfig(0.76, 1, 23, 23, True, 3, 18), 11017, 1200),
    LevelPreset("18 - Endurance", game_config.DifficultyStaminaConfig(0.80, 1, 25, 23, True, 3, 18), 11018, 1250),
    LevelPreset("19 - Expert", game_config.DifficultyStaminaConfig(0.85, 1, 25, 25, True, 3, 20), 11019, 1300),
    LevelPreset("20 - Final Maze", game_config.DifficultyStaminaConfig(0.90, 1, 27, 25, True, 3, 20), 11020, 1400),
)


def main() -> None:
    pygame.init()
    pygame.display.set_caption("Difficulty Stamina Maze")
    screen = pygame.display.set_mode(MENU_SIZE)
    fonts = {
        "title": pygame.font.SysFont("consolas", 32, bold=True),
        "big": pygame.font.SysFont("consolas", 22, bold=True),
        "body": pygame.font.SysFont("consolas", 16),
        "small": pygame.font.SysFont("consolas", 13),
    }
    tiles = pm.load_tiles()
    clock = pygame.time.Clock()
    screen_mode = "main_menu"
    selected_menu = 0
    selected_level = 0
    custom_fields = make_custom_fields()
    active_field = 0
    session: PlaySession | None = None

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if screen_mode == "main_menu":
                selected_menu, screen_mode = handle_main_menu_event(event, selected_menu)
            elif screen_mode == "custom_setup":
                active_field, screen_mode, maybe_session = handle_custom_event(
                    event,
                    screen,
                    fonts,
                    tiles,
                    custom_fields,
                    active_field,
                )
                if maybe_session is not None:
                    session = maybe_session
                    screen = resize_for_session(session)
                    tiles = pm.load_tiles()
                    screen_mode = "playing"
            elif screen_mode == "level_select":
                selected_level, screen_mode, maybe_session = handle_level_event(
                    event,
                    screen,
                    fonts,
                    tiles,
                    selected_level,
                )
                if maybe_session is not None:
                    session = maybe_session
                    screen = resize_for_session(session)
                    tiles = pm.load_tiles()
                    screen_mode = "playing"
            elif screen_mode == "playing" and session is not None:
                screen_mode, session, screen = handle_play_event(event, screen, fonts, tiles, session)

        if screen_mode == "main_menu":
            if screen.get_size() != MENU_SIZE:
                screen = pygame.display.set_mode(MENU_SIZE)
            draw_main_menu(screen, fonts, selected_menu)
        elif screen_mode == "custom_setup":
            if screen.get_size() != MENU_SIZE:
                screen = pygame.display.set_mode(MENU_SIZE)
            draw_custom_setup(screen, fonts, custom_fields, active_field)
        elif screen_mode == "level_select":
            if screen.get_size() != MENU_SIZE:
                screen = pygame.display.set_mode(MENU_SIZE)
            draw_level_select(screen, fonts, selected_level)
        elif screen_mode == "playing" and session is not None:
            draw_play_session(screen, fonts, tiles, session)

        pygame.display.flip()
        clock.tick(60)


def make_custom_fields() -> list[InputField]:
    config = game_config.get_difficulty_stamina_config()
    return [
        InputField("difficulty", "Difficulty", f"{config.target_agent_difficulty:.2f}", "0.0 - 1.0"),
        InputField("vision", "Vision radius", str(config.player_vision_radius), "1 - 5"),
        InputField("width", "Maze width", str(config.grid_width), "9 - 31, odd recommended"),
        InputField("height", "Maze height", str(config.grid_height), "9 - 25, odd recommended"),
        InputField("door_key", "Door requires key", "1" if config.door_requires_key else "0", "1=yes, 0=no"),
        InputField("stamina_count", "Stamina count", str(config.stamina_item_count), "0 - 3"),
        InputField("stamina_value", "Stamina value", str(config.stamina_item_value), "1 - 50"),
        InputField("seed", "Seed", "0", "0=random, otherwise fixed integer"),
    ]


def handle_main_menu_event(event: pygame.event.Event, selected_menu: int) -> tuple[int, str]:
    options_count = 2

    if event.type != pygame.KEYDOWN:
        return selected_menu, "main_menu"

    if event.key in (pygame.K_q, pygame.K_ESCAPE):
        pygame.quit()
        sys.exit()

    if event.key in (pygame.K_UP, pygame.K_w):
        return (selected_menu - 1) % options_count, "main_menu"

    if event.key in (pygame.K_DOWN, pygame.K_s):
        return (selected_menu + 1) % options_count, "main_menu"

    if event.key == pygame.K_1:
        return 0, "custom_setup"

    if event.key == pygame.K_2:
        return 1, "level_select"

    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
        return selected_menu, "custom_setup" if selected_menu == 0 else "level_select"

    return selected_menu, "main_menu"


def handle_custom_event(
    event: pygame.event.Event,
    screen: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    tiles: dict[str, pygame.Surface],
    fields: list[InputField],
    active_field: int,
) -> tuple[int, str, PlaySession | None]:
    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE:
            return active_field, "main_menu", None

        if event.key in (pygame.K_TAB, pygame.K_DOWN):
            return (active_field + 1) % len(fields), "custom_setup", None

        if event.key == pygame.K_UP:
            return (active_field - 1) % len(fields), "custom_setup", None

        if event.key == pygame.K_BACKSPACE:
            fields[active_field].value = fields[active_field].value[:-1]
            return active_field, "custom_setup", None

        if event.key == pygame.K_RETURN:
            if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                return active_field, "custom_setup", None

            settings, seed = parse_custom_fields(fields)
            session = generate_session(
                settings=settings,
                seed=seed,
                mcmc_steps=CUSTOM_MCMC_STEPS,
                mode="custom",
                level_index=None,
                screen=screen,
                fonts=fonts,
                tiles=tiles,
            )
            return active_field, "playing", session

    if event.type == pygame.TEXTINPUT:
        text = event.text
        if text and all(char in "0123456789.-" for char in text):
            fields[active_field].value += text

    return active_field, "custom_setup", None


def handle_level_event(
    event: pygame.event.Event,
    screen: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    tiles: dict[str, pygame.Surface],
    selected_level: int,
) -> tuple[int, str, PlaySession | None]:
    if event.type != pygame.KEYDOWN:
        return selected_level, "level_select", None

    if event.key == pygame.K_ESCAPE:
        return selected_level, "main_menu", None

    if event.key in (pygame.K_UP, pygame.K_w):
        return (selected_level - 1) % len(LEVELS), "level_select", None

    if event.key in (pygame.K_DOWN, pygame.K_s):
        return (selected_level + 1) % len(LEVELS), "level_select", None

    if event.key in (pygame.K_PAGEUP,):
        return max(0, selected_level - 5), "level_select", None

    if event.key in (pygame.K_PAGEDOWN,):
        return min(len(LEVELS) - 1, selected_level + 5), "level_select", None

    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
        preset = LEVELS[selected_level]
        session = generate_session(
            settings=preset.config,
            seed=preset.seed,
            mcmc_steps=preset.mcmc_steps,
            mode="level",
            level_index=selected_level,
            screen=screen,
            fonts=fonts,
            tiles=tiles,
        )
        return selected_level, "playing", session

    return selected_level, "level_select", None


def handle_play_event(
    event: pygame.event.Event,
    screen: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    tiles: dict[str, pygame.Surface],
    session: PlaySession,
) -> tuple[str, PlaySession, pygame.Surface]:
    if event.type != pygame.KEYDOWN:
        return "playing", session, screen

    if event.key in (pygame.K_ESCAPE, pygame.K_m):
        return "main_menu", session, pygame.display.set_mode(MENU_SIZE)

    if event.key == pygame.K_q:
        pygame.quit()
        sys.exit()

    if event.key == pygame.K_r:
        session.game = reset_game(session.game.mc_state)
        session.item_pos_map = None
        screen = resize_for_session(session)
        reload_tiles(tiles)
        return "playing", session, screen

    if event.key == pygame.K_p and session.game.status == "playing":
        session.game = surrender_game(session.game)
        session.item_pos_map = None
        return "playing", session, screen

    if (
        event.key == pygame.K_n
        and session.mode == "level"
        and session.game.status == "won"
        and session.level_index is not None
        and session.level_index < len(LEVELS) - 1
    ):
        next_index = session.level_index + 1
        preset = LEVELS[next_index]
        next_session = generate_session(
            settings=preset.config,
            seed=preset.seed,
            mcmc_steps=preset.mcmc_steps,
            mode="level",
            level_index=next_index,
            screen=screen,
            fonts=fonts,
            tiles=tiles,
        )
        screen = resize_for_session(next_session)
        reload_tiles(tiles)
        return "playing", next_session, screen

    if session.game.status == "playing":
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
            result = pm.try_move(session.game, *move)

            if result is not None:
                session.game = result
                session.item_pos_map = None

    return "playing", session, screen


def parse_custom_fields(fields: list[InputField]) -> tuple[game_config.DifficultyStaminaConfig, int]:
    values = {field.key: field.value.strip() for field in fields}
    seed = parse_int(values.get("seed", ""), RANDOM_SEED_SENTINEL)

    if seed == RANDOM_SEED_SENTINEL:
        seed = random.randrange(1, 1_000_000_000)

    config = game_config.DifficultyStaminaConfig(
        target_agent_difficulty=parse_float(values.get("difficulty", ""), game_config.TARGET_AGENT_DIFFICULTY),
        player_vision_radius=parse_int(values.get("vision", ""), game_config.PLAYER_VISION_RADIUS),
        grid_width=parse_int(values.get("width", ""), game_config.GRID_WIDTH),
        grid_height=parse_int(values.get("height", ""), game_config.GRID_HEIGHT),
        door_requires_key=parse_bool(values.get("door_key", ""), game_config.DOOR_REQUIRES_KEY),
        stamina_item_count=parse_int(values.get("stamina_count", ""), game_config.STAMINA_ITEM_COUNT),
        stamina_item_value=parse_int(values.get("stamina_value", ""), game_config.STAMINA_ITEM_VALUE),
    )
    return game_config.clamp_difficulty_stamina_config(config), seed


def generate_session(
    *,
    settings: game_config.DifficultyStaminaConfig,
    seed: int,
    mcmc_steps: int,
    mode: str,
    level_index: int | None,
    screen: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    tiles: dict[str, pygame.Surface],
) -> PlaySession:
    settings = game_config.clamp_difficulty_stamina_config(settings)
    draw_loading(screen, fonts, f"Generating maze... seed={seed}")
    pygame.display.flip()
    settings = bp.apply_difficulty_stamina_config(settings)
    pm.FOG_RADIUS = settings.player_vision_radius
    bp.MCMC_STEPS = mcmc_steps
    bp.RANDOM_SEED = seed
    random.seed(seed)

    print(f"\n[difficulty_game] Generating {mode} map seed={seed}")
    print(f"[difficulty_game] settings={settings}")
    _, _, best_state, best_energy, _ = bp.run_baseline_mcmc(
        energy_function=bp.get_energy_function(),
    )
    print(f"[difficulty_game] energy={best_energy:.3f}")
    print(bp.render_ascii_map(best_state))
    print(bp.get_energy_breakdown(best_state))
    print(bp.get_solution_summary(best_state, label="best"))

    return PlaySession(
        game=reset_game(best_state),
        settings=settings,
        seed=seed,
        mcmc_steps=mcmc_steps,
        mode=mode,
        level_index=level_index,
        item_pos_map=None,
    )


def reset_game(state: bp.BaselineState) -> pm.GameState:
    visible = pm.compute_visible_cells(
        state.grid,
        state.start,
        pm.FOG_RADIUS,
    )
    return pm.GameState(
        mc_state=state,
        player_pos=state.start,
        stamina=state.initial_stamina,
        max_stamina=state.initial_stamina,
        has_key=False,
        door_open=not state.locked_door,
        collected_items=set(),
        visible_cells=visible,
        seen_cells=set(visible),
        status="playing",
    )


def surrender_game(game: pm.GameState) -> pm.GameState:
    return pm.GameState(
        mc_state=game.mc_state,
        player_pos=game.player_pos,
        stamina=game.stamina,
        max_stamina=game.max_stamina,
        has_key=game.has_key,
        door_open=game.door_open,
        collected_items=set(game.collected_items),
        visible_cells=set(game.visible_cells),
        seen_cells=set(game.seen_cells),
        status="lost",
        message="Pes edildi. Cozum replay olarak gosteriliyor.",
        replay_path=pm.compute_replay_path(game.mc_state),
        replay_frame=0,
    )


def resize_for_session(session: PlaySession) -> pygame.Surface:
    grid = session.game.mc_state.grid
    update_play_scale_for_grid(grid)
    map_width = len(grid[0]) * pm.TILE_PIXELS
    map_height = len(grid) * pm.TILE_PIXELS
    return pygame.display.set_mode((map_width, map_height + pm.HUD_HEIGHT))


def reload_tiles(tiles: dict[str, pygame.Surface]) -> None:
    tiles.clear()
    tiles.update(pm.load_tiles())


def update_play_scale_for_grid(grid: list[list[int]]) -> None:
    height = len(grid)
    width = len(grid[0]) if height else 0
    max_width, max_height = MAX_PLAY_WINDOW_SIZE
    available_height = max(1, max_height - pm.HUD_HEIGHT)
    scale_by_width = max_width // max(1, width * pm.TILE_SIZE)
    scale_by_height = available_height // max(1, height * pm.TILE_SIZE)
    scale = min(PREFERRED_PLAY_SCALE, scale_by_width, scale_by_height)
    scale = max(MIN_PLAY_SCALE, scale)
    pm.SCALE = scale
    pm.TILE_PIXELS = pm.TILE_SIZE * pm.SCALE
    pm.ITEM_PIXELS = pm.ITEM_SIZE * pm.SCALE


def draw_main_menu(screen: pygame.Surface, fonts: dict[str, pygame.font.Font], selected: int) -> None:
    screen.fill((14, 18, 28))
    title = fonts["title"].render("Difficulty Stamina Maze", True, (235, 235, 220))
    screen.blit(title, (60, 60))
    subtitle = fonts["body"].render("Config-driven Monte Carlo maze game", True, (140, 160, 180))
    screen.blit(subtitle, (62, 104))

    options = ("Custom map", "20-level campaign")
    for index, option in enumerate(options):
        y = 190 + index * 68
        selected_color = (250, 190, 80) if index == selected else (210, 220, 230)
        prefix = "> " if index == selected else "  "
        screen.blit(fonts["big"].render(prefix + option, True, selected_color), (90, y))

    hints = (
        "Up/Down: Select",
        "Enter: Open",
        "1: Custom map",
        "2: Level campaign",
        "Q/Esc: Quit",
    )
    draw_hint_block(screen, fonts, hints, 90, 380)


def draw_custom_setup(
    screen: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    fields: list[InputField],
    active_index: int,
) -> None:
    screen.fill((12, 20, 18))
    screen.blit(fonts["title"].render("Custom Map Config", True, (230, 240, 220)), (60, 42))
    screen.blit(
        fonts["body"].render("Edit values, then press Enter on any field to generate.", True, (140, 170, 150)),
        (62, 82),
    )

    for index, field in enumerate(fields):
        y = 135 + index * 52
        active = index == active_index
        box_color = (240, 185, 75) if active else (80, 100, 95)
        label_color = (235, 235, 220) if active else (180, 195, 185)
        pygame.draw.rect(screen, box_color, (330, y - 8, 170, 34), 2)
        screen.blit(fonts["body"].render(field.label, True, label_color), (75, y))
        screen.blit(fonts["body"].render(field.value or "_", True, (230, 230, 210)), (342, y))
        screen.blit(fonts["small"].render(field.hint, True, (110, 145, 130)), (520, y + 2))

    hints = (
        "Tab/Up/Down: Change field",
        "Backspace/Text: Edit",
        "Enter: Generate",
        "Esc: Main menu",
    )
    draw_hint_block(screen, fonts, hints, 75, 585)


def draw_level_select(screen: pygame.Surface, fonts: dict[str, pygame.font.Font], selected: int) -> None:
    screen.fill((18, 16, 28))
    screen.blit(fonts["title"].render("20-Level Campaign", True, (235, 230, 245)), (60, 34))
    screen.blit(fonts["body"].render("Fixed seed + config presets. Difficulty grows over time.", True, (160, 150, 185)), (62, 75))

    start = max(0, min(selected - 5, len(LEVELS) - 10))
    for visible_index, level_index in enumerate(range(start, min(len(LEVELS), start + 10))):
        preset = LEVELS[level_index]
        y = 120 + visible_index * 46
        active = level_index == selected
        color = (250, 190, 80) if active else (215, 215, 230)
        prefix = "> " if active else "  "
        text = (
            f"{prefix}{preset.name}  "
            f"D={preset.config.target_agent_difficulty:.2f} "
            f"{preset.config.grid_width}x{preset.config.grid_height} "
            f"V={preset.config.player_vision_radius} "
            f"S={preset.config.stamina_item_count}"
        )
        screen.blit(fonts["body"].render(text, True, color), (80, y))

    hints = (
        "Up/Down: Select level",
        "PageUp/PageDown: Jump",
        "Enter: Start selected level",
        "Esc: Main menu",
    )
    draw_hint_block(screen, fonts, hints, 80, 610)


def draw_play_session(
    screen: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    tiles: dict[str, pygame.Surface],
    session: PlaySession,
) -> None:
    replay_pos = None
    replay_collected = None
    replay_door_open = None

    if session.game.status == "lost" and session.game.replay_path:
        if session.item_pos_map is None:
            session.item_pos_map = {
                item.position: index
                for index, item in enumerate(session.game.mc_state.items)
            }

        step = (session.game.replay_frame // pm.REPLAY_FRAMES_PER_STEP) % len(session.game.replay_path)
        replay_pos = session.game.replay_path[step]
        replay_collected = {
            session.item_pos_map[position]
            for position in session.game.replay_path[: step + 1]
            if position in session.item_pos_map
        }
        replay_door_open = any(
            session.game.mc_state.items[item_index].kind == "key"
            for item_index in replay_collected
        ) or not session.game.mc_state.locked_door
        session.game.replay_frame += 1

    map_height = len(session.game.mc_state.grid) * pm.TILE_PIXELS
    pm.draw_map(
        screen,
        tiles,
        session.game,
        replay_player_pos=replay_pos,
        replay_collected=replay_collected,
        replay_door_open=replay_door_open,
    )
    pm.draw_hud(screen, fonts["small"], session.game, map_height)
    draw_play_overlay(screen, fonts, session)


def draw_play_overlay(screen: pygame.Surface, fonts: dict[str, pygame.font.Font], session: PlaySession) -> None:
    lines = [
        f"Mode: {session.mode}  Seed: {session.seed}  D={session.settings.target_agent_difficulty:.2f}",
        "P: Surrender/replay   R: Retry same map   M/Esc: Menu   Q: Quit",
    ]

    if session.mode == "level" and session.level_index is not None:
        lines[0] = f"Level {session.level_index + 1}/20  {LEVELS[session.level_index].name}  " + lines[0]

        if session.game.status == "won" and session.level_index < len(LEVELS) - 1:
            lines.append("N: Next level")
        elif session.game.status == "won":
            lines.append("Campaign complete.")

    overlay = pygame.Surface((screen.get_width(), 48), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 135))
    screen.blit(overlay, (0, 0))

    for index, line in enumerate(lines[:3]):
        screen.blit(fonts["small"].render(line, True, (235, 235, 220)), (10, 6 + index * 15))


def draw_loading(screen: pygame.Surface, fonts: dict[str, pygame.font.Font], message: str) -> None:
    screen.fill((10, 12, 18))
    text = fonts["big"].render(message, True, (230, 210, 110))
    sub = fonts["body"].render("Monte Carlo is running. This can take a few seconds.", True, (155, 165, 180))
    screen.blit(text, (screen.get_width() // 2 - text.get_width() // 2, screen.get_height() // 2 - 30))
    screen.blit(sub, (screen.get_width() // 2 - sub.get_width() // 2, screen.get_height() // 2 + 6))


def draw_hint_block(
    screen: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    lines: tuple[str, ...],
    x: int,
    y: int,
) -> None:
    for index, line in enumerate(lines):
        screen.blit(fonts["body"].render(line, True, (145, 155, 170)), (x, y + index * 26))


def parse_float(value: str, fallback: float) -> float:
    try:
        return float(value)
    except ValueError:
        return fallback


def parse_int(value: str, fallback: int) -> int:
    try:
        return int(value)
    except ValueError:
        return fallback


def parse_bool(value: str, fallback: bool) -> bool:
    if value.strip() in {"1", "true", "True", "yes", "y"}:
        return True

    if value.strip() in {"0", "false", "False", "no", "n"}:
        return False

    return fallback


if __name__ == "__main__":
    main()
