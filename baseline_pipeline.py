from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Callable

from utils.energy_functions import make_path_length_energy
from utils.hard_constraints import (
    can_open_cell_preserve_connectivity,
    can_remove_cell_preserve_connectivity,
    is_hc1_satisfied,
    is_hc2_satisfied,
    would_create_open_2x2,
)
from utils.map_analysis import (
    choose_farthest_reachable_cell,
    copy_grid,
    is_walkable,
    render_ascii_grid,
)
from utils.maze_generation import MAP_HEIGHT, MAP_WIDTH, generate_maze_map

RANDOM_SEED = 42

GRID_WIDTH = 12
GRID_HEIGHT = 12
START_POS = (1, 1)
TARGET_PATH_LENGTH =50
ENERGY_FUNCTION = make_path_length_energy(TARGET_PATH_LENGTH)

MCMC_STEPS = 200
TEMPERATURE = 2.0
MAX_PROPOSAL_ATTEMPTS = 40
LOG_EVERY = 20


Grid = list[list[int]]
Position = tuple[int, int]
EnergyFunction = Callable[["BaselineState"], float]


@dataclass
class BaselineState:
    grid: Grid
    start: Position
    door: Position


@dataclass
class StepStats:
    proposals: int = 0
    local_invalid_moves: int = 0
    constraint_rejections: int = 0
    mh_rejections: int = 0
    accepted: int = 0


def choose_door_position(grid: Grid, start: Position) -> Position:
    return choose_farthest_reachable_cell(grid, start)


def is_state_valid(state: BaselineState) -> bool:
    start_row, start_col = state.start
    door_row, door_col = state.door

    if not is_walkable(state.grid, start_row, start_col):
        return False

    if not is_walkable(state.grid, door_row, door_col):
        return False

    if not is_hc2_satisfied(state.grid):
        return False

    return is_hc1_satisfied(state.grid, start_row, start_col)


def create_initial_state() -> BaselineState:
    grid = generate_maze_map(GRID_WIDTH, GRID_HEIGHT)
    door = choose_door_position(grid, START_POS)
    state = BaselineState(grid=grid, start=START_POS, door=door)

    if not is_state_valid(state):
        raise ValueError("Generated initial state is not HC1/HC2 valid.")

    return state

def pick_random_edit_cell(state: BaselineState) -> Position:
    height = len(state.grid)
    width = len(state.grid[0])

    while True:
        row = random.randint(1, height - 2)
        col = random.randint(1, width - 2)

        if (row, col) == state.start or (row, col) == state.door:
            continue

        return row, col


def try_propose_candidate(state: BaselineState) -> BaselineState | None:
    row, col = pick_random_edit_cell(state)
    cell_value = state.grid[row][col]

    if cell_value == 1:
        if would_create_open_2x2(state.grid, row, col):
            return None

        if not can_open_cell_preserve_connectivity(state.grid, row, col):
            return None

        candidate_grid = copy_grid(state.grid)
        candidate_grid[row][col] = 0
        return BaselineState(candidate_grid, state.start, state.door)

    candidate_grid = copy_grid(state.grid)
    candidate_grid[row][col] = 1

    if can_remove_cell_preserve_connectivity(state.grid, row, col):
        return BaselineState(candidate_grid, state.start, state.door)

    if not is_hc1_satisfied(candidate_grid, state.start[0], state.start[1]):
        return None

    return BaselineState(candidate_grid, state.start, state.door)


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
    return render_ascii_grid(state.grid, start=state.start, door=state.door)


def run_baseline_mcmc(
    energy_function: EnergyFunction,
) -> tuple[BaselineState, float, BaselineState, float, StepStats]:
    current_state = create_initial_state()
    current_energy = energy_function(current_state)
    best_state = BaselineState(copy_grid(current_state.grid), current_state.start, current_state.door)
    best_energy = current_energy
    stats = StepStats()

    print("[Initial state]")
    print(render_ascii_map(current_state))
    print(f"Initial energy: {current_energy}")
    print(f"Door position: {current_state.door}")

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
                best_state = BaselineState(
                    copy_grid(current_state.grid),
                    current_state.start,
                    current_state.door,
                )
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
