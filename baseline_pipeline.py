from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Callable

from utils.energy_functions import make_path_length_energy
from utils.hard_constraints import (
    StaminaOnlyHC3GraphCache,
    StaminaOnlyHC3Problem,
    can_open_cell_preserve_connectivity,
    can_remove_cell_preserve_connectivity,
    is_hc1_satisfied,
    is_hc2_satisfied,
    is_stamina_only_hc3_satisfied,
    would_create_open_2x2,
)
from utils.map_analysis import copy_grid, is_walkable
from utils.map_entities import (
    ItemPlacement,
    choose_door_position,
    get_walkable_positions,
    place_items,
)
from utils.maze_generation import generate_maze_map

RANDOM_SEED = 10

GRID_WIDTH = 15
GRID_HEIGHT = 15
START_POS = (1, 1)
TARGET_PATH_LENGTH = 30
MAX_INITIAL_STATE_ATTEMPTS = 200
ENERGY_FUNCTION = make_path_length_energy(TARGET_PATH_LENGTH)
GAME_MODE = "stamina_only"

MCMC_STEPS = 1000
TEMPERATURE = 2.0
MAX_PROPOSAL_ATTEMPTS = 40
LOG_EVERY = 20


Grid = list[list[int]]
Position = tuple[int, int]
EnergyFunction = Callable[["BaselineState"], float]
HC3_CACHE = StaminaOnlyHC3GraphCache()


@dataclass(frozen=True)
class ModeConfig:
    name: str
    uses_stamina_solver: bool
    initial_stamina: int
    locked_door: bool
    item_kinds: tuple[str, ...]
    proposal_move_types: tuple[str, ...]


MODE_CONFIGS = {
    "door_only": ModeConfig(
        name="door_only",
        uses_stamina_solver=False,
        initial_stamina=0,
        locked_door=False,
        item_kinds=(),
        proposal_move_types=("topology",),
    ),
    "stamina_only": ModeConfig(
        name="stamina_only",
        uses_stamina_solver=True,
        initial_stamina=20,
        locked_door=True,
        item_kinds=("stamina", "stamina", "key"),
        proposal_move_types=("topology", "item_move", "toggle_door"),
    ),
}


@dataclass
class BaselineState:
    grid: Grid
    start: Position
    door: Position
    items: tuple[ItemPlacement, ...]
    initial_stamina: int
    locked_door: bool


@dataclass
class StepStats:
    proposals: int = 0
    local_invalid_moves: int = 0
    constraint_rejections: int = 0
    mh_rejections: int = 0
    accepted: int = 0


def get_mode_config() -> ModeConfig:
    return MODE_CONFIGS[GAME_MODE]


def build_hc3_problem(state: BaselineState) -> StaminaOnlyHC3Problem:
    return StaminaOnlyHC3Problem(
        grid=state.grid,
        start=state.start,
        door=state.door,
        items=state.items,
        initial_stamina=state.initial_stamina,
        locked_door=state.locked_door,
    )


def is_state_valid(state: BaselineState) -> bool:
    mode_config = get_mode_config()
    start_row, start_col = state.start
    door_row, door_col = state.door

    if not is_walkable(state.grid, start_row, start_col):
        return False

    if not is_walkable(state.grid, door_row, door_col):
        return False

    if not is_hc2_satisfied(state.grid):
        return False

    if not is_hc1_satisfied(state.grid, start_row, start_col):
        return False

    if not mode_config.uses_stamina_solver:
        return True

    return is_stamina_only_hc3_satisfied(build_hc3_problem(state), cache=HC3_CACHE)


def create_initial_state() -> BaselineState:
    mode_config = get_mode_config()

    for _ in range(MAX_INITIAL_STATE_ATTEMPTS):
        grid = generate_maze_map(GRID_WIDTH, GRID_HEIGHT)
        door = choose_door_position(grid, START_POS)
        items = place_items(
            grid,
            item_kinds=mode_config.item_kinds,
            start=START_POS,
            door=door,
        )
        state = BaselineState(
            grid=grid,
            start=START_POS,
            door=door,
            items=items,
            initial_stamina=mode_config.initial_stamina,
            locked_door=mode_config.locked_door,
        )

        if is_state_valid(state):
            return state

    raise ValueError("Could not generate an initial HC1/HC2/HC3-valid state.")


def get_protected_positions(state: BaselineState) -> set[Position]:
    return {state.start, state.door, *(item.position for item in state.items)}


def clone_state_with_grid(state: BaselineState, grid: Grid) -> BaselineState:
    return BaselineState(
        grid=grid,
        start=state.start,
        door=state.door,
        items=state.items,
        initial_stamina=state.initial_stamina,
        locked_door=state.locked_door,
    )


def clone_state(
    state: BaselineState,
    *,
    grid: Grid | None = None,
    items: tuple[ItemPlacement, ...] | None = None,
    locked_door: bool | None = None,
) -> BaselineState:
    return BaselineState(
        grid=grid if grid is not None else state.grid,
        start=state.start,
        door=state.door,
        items=items if items is not None else state.items,
        initial_stamina=state.initial_stamina,
        locked_door=state.locked_door if locked_door is None else locked_door,
    )


def pick_random_edit_cell(state: BaselineState) -> Position:
    height = len(state.grid)
    width = len(state.grid[0])
    protected_positions = get_protected_positions(state)

    while True:
        row = random.randint(1, height - 2)
        col = random.randint(1, width - 2)

        if (row, col) in protected_positions:
            continue

        return row, col


def pick_random_item_index(state: BaselineState) -> int | None:
    if not state.items:
        return None

    return random.randrange(len(state.items))


def pick_random_item_destination(state: BaselineState, item_index: int) -> Position | None:
    blocked_positions = get_protected_positions(state) - {state.items[item_index].position}
    walkable_positions = get_walkable_positions(state.grid, blocked_positions=blocked_positions)

    if not walkable_positions:
        return None

    return random.choice(walkable_positions)


def propose_topology_move(state: BaselineState) -> BaselineState | None:
    row, col = pick_random_edit_cell(state)
    cell_value = state.grid[row][col]

    if cell_value == 1:
        if would_create_open_2x2(state.grid, row, col):
            return None

        if not can_open_cell_preserve_connectivity(state.grid, row, col):
            return None

        candidate_grid = copy_grid(state.grid)
        candidate_grid[row][col] = 0
        candidate_state = clone_state_with_grid(state, candidate_grid)
        return candidate_state if is_state_valid(candidate_state) else None

    candidate_grid = copy_grid(state.grid)
    candidate_grid[row][col] = 1

    if not can_remove_cell_preserve_connectivity(state.grid, row, col):
        if not is_hc1_satisfied(candidate_grid, state.start[0], state.start[1]):
            return None

    candidate_state = clone_state_with_grid(state, candidate_grid)
    return candidate_state if is_state_valid(candidate_state) else None


def propose_item_move(state: BaselineState) -> BaselineState | None:
    item_index = pick_random_item_index(state)

    if item_index is None:
        return None

    destination = pick_random_item_destination(state, item_index)

    if destination is None or destination == state.items[item_index].position:
        return None

    moved_item = ItemPlacement(
        kind=state.items[item_index].kind,
        position=destination,
        value=state.items[item_index].value,
    )
    updated_items = list(state.items)
    updated_items[item_index] = moved_item
    candidate_state = clone_state(state, items=tuple(updated_items))
    return candidate_state if is_state_valid(candidate_state) else None


def propose_toggle_door_move(state: BaselineState) -> BaselineState | None:
    candidate_state = clone_state(state, locked_door=not state.locked_door)
    return candidate_state if is_state_valid(candidate_state) else None


def try_propose_candidate(state: BaselineState) -> BaselineState | None:
    mode_config = get_mode_config()
    move_type = random.choice(mode_config.proposal_move_types)

    if move_type == "topology":
        return propose_topology_move(state)

    if move_type == "item_move":
        return propose_item_move(state)

    if move_type == "toggle_door":
        return propose_toggle_door_move(state)

    raise ValueError(f"Unknown proposal move type: {move_type}")


def propose_candidate(state: BaselineState) -> tuple[BaselineState | None, int]:
    invalid_attempts = 0

    for _ in range(MAX_PROPOSAL_ATTEMPTS):
        candidate = try_propose_candidate(state)

        if candidate is None:
            invalid_attempts += 1
            continue

        return candidate, invalid_attempts

    return None, invalid_attempts


def should_accept_move(current_energy: float, candidate_energy: float, temperature: float) -> bool:
    if candidate_energy <= current_energy:
        return True

    if temperature <= 0:
        return False

    acceptance_probability = math.exp(-(candidate_energy - current_energy) / temperature)
    return random.random() < acceptance_probability


def render_ascii_map(state: BaselineState) -> str:
    item_positions = {item.position: item for item in state.items}
    lines = []

    for row_index, row in enumerate(state.grid):
        chars = []

        for col_index, cell in enumerate(row):
            position = (row_index, col_index)

            if position == state.start:
                chars.append("S")
            elif position == state.door:
                chars.append("d" if state.locked_door else "D")
            elif position in item_positions:
                item = item_positions[position]
                chars.append("K" if item.kind == "key" else "T")
            elif cell == 0:
                chars.append(".")
            else:
                chars.append("#")

        lines.append(" ".join(chars))

    return "\n".join(lines)


def run_baseline_mcmc(
    energy_function: EnergyFunction,
) -> tuple[BaselineState, float, BaselineState, float, StepStats]:
    mode_config = get_mode_config()
    current_state = create_initial_state()
    current_energy = energy_function(current_state)
    best_state = clone_state_with_grid(current_state, copy_grid(current_state.grid))
    best_energy = current_energy
    stats = StepStats()

    print("[Initial state]")
    print(render_ascii_map(current_state))
    print(f"Initial energy: {current_energy}")
    print(f"Mode: {mode_config.name}")
    print(f"Door position: {current_state.door}")
    print(f"Locked door: {current_state.locked_door}")
    print(f"Initial stamina: {current_state.initial_stamina}")
    print(f"Items: {[(item.kind, item.position, item.value) for item in current_state.items]}")

    for step_index in range(1, MCMC_STEPS + 1):
        stats.proposals += 1
        candidate_state, invalid_attempts = propose_candidate(current_state)
        stats.local_invalid_moves += invalid_attempts

        if candidate_state is None:
            stats.constraint_rejections += 1
            continue

        candidate_energy = energy_function(candidate_state)

        if should_accept_move(current_energy, candidate_energy, TEMPERATURE):
            current_state = candidate_state
            current_energy = candidate_energy
            stats.accepted += 1

            if current_energy < best_energy:
                best_state = clone_state_with_grid(current_state, copy_grid(current_state.grid))
                best_energy = current_energy
        else:
            stats.mh_rejections += 1

        if step_index % LOG_EVERY == 0:
            print(
                f"step={step_index} energy={current_energy} "
                f"best_energy={best_energy} "
                f"accepted={stats.accepted} "
                f"local_invalid_moves={stats.local_invalid_moves} "
                f"constraint_rejections={stats.constraint_rejections} "
                f"mh_rejections={stats.mh_rejections}"
            )

    return current_state, current_energy, best_state, best_energy, stats


def main() -> None:
    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)

    final_state, final_energy, best_state, best_energy, stats = run_baseline_mcmc(
        energy_function=ENERGY_FUNCTION,
    )

    print("\n[Final state]")
    print(render_ascii_map(final_state))
    print(f"Final energy: {final_energy}")
    print(f"Final door position: {final_state.door}")
    print("\n[Best state visited]")
    print(render_ascii_map(best_state))
    print(f"Best energy: {best_energy}")
    print(
        "Stats: "
        f"proposals={stats.proposals}, "
        f"accepted={stats.accepted}, "
        f"local_invalid_moves={stats.local_invalid_moves}, "
        f"constraint_rejections={stats.constraint_rejections}, "
        f"mh_rejections={stats.mh_rejections}"
    )


if __name__ == "__main__":
    main()
