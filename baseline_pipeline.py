from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Callable

from utils.energy_functions import (
    AgentDifficultyConfig,
    make_path_length_energy,
    make_stamina_agent_difficulty_energy,
    make_stamina_aware_baseline_energy,
    path_length_energy_breakdown,
    stamina_agent_difficulty_energy_breakdown,
    stamina_aware_baseline_energy_breakdown,
)
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
from utils.map_analysis import bfs_distances, copy_grid, is_walkable, iter_neighbors
from utils.map_entities import (
    get_default_item_value,
    ItemPlacement,
    choose_door_position,
    get_walkable_positions,
    place_items,
)
from utils.maze_generation import generate_maze_map

RANDOM_SEED = 42 #5

GRID_WIDTH = 15
GRID_HEIGHT = 15
START_POS = (1, 1)
TARGET_PATH_LENGTH = 52
TARGET_FINAL_STAMINA = 10
TARGET_AGENT_DIFFICULTY = 0.9
AGENT_DIFFICULTY_WEIGHT = 20.0
SEGMENT_BALANCE_WEIGHT = 15.0
DEAD_SEGMENT_WEIGHT = 0
FINAL_STAMINA_WEIGHT = 10.0
FINAL_STAMINA_TARGET_FACTOR = 0.8
AGENTS_PER_SEGMENT = 30
AGENT_DIFFICULTY_SEED = 12345
MAX_INITIAL_STATE_ATTEMPTS = 200
MAX_ITEM_PLACEMENT_ATTEMPTS = 100
GAME_MODE = "stamina_only"  # "door_only" or "stamina_only"
STAMINA_ENERGY_MODEL = "agent_difficulty"  # "baseline" or "agent_difficulty"

MCMC_STEPS = 1000
TEMPERATURE = 2.0
MAX_PROPOSAL_ATTEMPTS = 40
LOG_EVERY = 20


Grid = list[list[int]]
Position = tuple[int, int]
EnergyFunction = Callable[["BaselineState"], float]
HC3_CACHE = StaminaOnlyHC3GraphCache()
DOOR_ONLY_ENERGY_FUNCTION = make_path_length_energy(TARGET_PATH_LENGTH)
AGENT_DIFFICULTY_CONFIG = AgentDifficultyConfig(
    agents_per_segment=AGENTS_PER_SEGMENT,
    random_seed=AGENT_DIFFICULTY_SEED,
)
STAMINA_ONLY_ENERGY_FUNCTION = make_stamina_aware_baseline_energy(
    target_path_length=TARGET_PATH_LENGTH,
    target_remaining_stamina=TARGET_FINAL_STAMINA,
)
STAMINA_AGENT_DIFFICULTY_ENERGY_FUNCTION = make_stamina_agent_difficulty_energy(
    target_agent_difficulty=TARGET_AGENT_DIFFICULTY,
    difficulty_weight=AGENT_DIFFICULTY_WEIGHT,
    segment_balance_weight=SEGMENT_BALANCE_WEIGHT,
    dead_segment_weight=DEAD_SEGMENT_WEIGHT,
    final_stamina_weight=FINAL_STAMINA_WEIGHT,
    final_stamina_target_factor=FINAL_STAMINA_TARGET_FACTOR,
    agent_config=AGENT_DIFFICULTY_CONFIG,
)


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
        proposal_move_types=("topology", "door_move"),
    ),
    "stamina_only": ModeConfig(
        name="stamina_only",
        uses_stamina_solver=True,
        initial_stamina=  50,#TARGET_PATH_LENGTH + TARGET_FINAL_STAMINA - 2* 6,  # Start with enough stamina to reach the door, then optimize from there.
        locked_door=True,
        item_kinds=("stamina", "stamina","key",), #"stamina", "stamina", 
        proposal_move_types=("topology", "item_move", "door_move"),
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


def get_energy_function() -> EnergyFunction:
    if GAME_MODE == "door_only":
        return DOOR_ONLY_ENERGY_FUNCTION

    if GAME_MODE == "stamina_only":
        if STAMINA_ENERGY_MODEL == "agent_difficulty":
            return STAMINA_AGENT_DIFFICULTY_ENERGY_FUNCTION

        if STAMINA_ENERGY_MODEL != "baseline":
            raise ValueError(f"Unknown stamina energy model: {STAMINA_ENERGY_MODEL}")

        return STAMINA_ONLY_ENERGY_FUNCTION

    raise ValueError(f"Unknown game mode: {GAME_MODE}")


def get_energy_breakdown(state: BaselineState) -> str:
    if GAME_MODE == "door_only":
        breakdown = path_length_energy_breakdown(
            state=state,
            target_path_length=TARGET_PATH_LENGTH,
        )
        return (
            f"target_path={breakdown.path_target} "
            f"path={breakdown.path_actual} "
            f"path_term={breakdown.path_term} "
            f"total={breakdown.total_energy}"
        )

    if GAME_MODE == "stamina_only":
        if STAMINA_ENERGY_MODEL == "agent_difficulty":
            breakdown = stamina_agent_difficulty_energy_breakdown(
                state=state,
                target_agent_difficulty=TARGET_AGENT_DIFFICULTY,
                difficulty_weight=AGENT_DIFFICULTY_WEIGHT,
                segment_balance_weight=SEGMENT_BALANCE_WEIGHT,
                dead_segment_weight=DEAD_SEGMENT_WEIGHT,
                final_stamina_weight=FINAL_STAMINA_WEIGHT,
                final_stamina_target_factor=FINAL_STAMINA_TARGET_FACTOR,
                agent_config=AGENT_DIFFICULTY_CONFIG,
            )
            return (
                f"target_agent_difficulty={breakdown.agent_difficulty_target} "
                f"main_route_difficulty={breakdown.agent_difficulty_actual} "
                f"main_route_success_rate={breakdown.agent_success_rate} "
                f"main_route_term={breakdown.agent_difficulty_term} "
                f"segment_success_std={breakdown.segment_balance_penalty} "
                f"segment_balance_score={breakdown.segment_balance_score} "
                f"segment_balance_term={breakdown.segment_balance_term} "
                f"dead_segment_ratio={breakdown.dead_segment_ratio} "
                f"dead_segment_term={breakdown.dead_segment_term} "
                f"target_weighted_final_stamina={breakdown.remaining_stamina_target} "
                f"weighted_final_stamina={breakdown.remaining_stamina_actual} "
                f"final_stamina_score={breakdown.remaining_stamina_score} "
                f"final_stamina_term={breakdown.remaining_stamina_term} "
                f"total={breakdown.total_energy}"
            )

        breakdown = stamina_aware_baseline_energy_breakdown(
            state=state,
            target_path_length=TARGET_PATH_LENGTH,
            target_remaining_stamina=TARGET_FINAL_STAMINA,
        )
        return (
            f"target_path={breakdown.path_target} "
            f"path={breakdown.path_actual} "
            f"path_term={breakdown.path_term} "
            f"target_final_stamina={breakdown.remaining_stamina_target} "
            f"final_stamina={breakdown.remaining_stamina_actual} "
            f"stamina_term={breakdown.remaining_stamina_term} "
            f"total={breakdown.total_energy}"
        )

    raise ValueError(f"Unknown game mode: {GAME_MODE}")


def get_agent_difficulty_summary(state: BaselineState, label: str = "state") -> str:
    if GAME_MODE != "stamina_only" or STAMINA_ENERGY_MODEL != "agent_difficulty":
        return f"Agent difficulty summary ({label}): not enabled."

    breakdown = stamina_agent_difficulty_energy_breakdown(
        state=state,
        target_agent_difficulty=TARGET_AGENT_DIFFICULTY,
        difficulty_weight=AGENT_DIFFICULTY_WEIGHT,
        segment_balance_weight=SEGMENT_BALANCE_WEIGHT,
        dead_segment_weight=DEAD_SEGMENT_WEIGHT,
        final_stamina_weight=FINAL_STAMINA_WEIGHT,
        final_stamina_target_factor=FINAL_STAMINA_TARGET_FACTOR,
        agent_config=AGENT_DIFFICULTY_CONFIG,
    )
    summary = breakdown.agent_difficulty_summary

    if summary is None:
        return f"Agent difficulty summary ({label}): unavailable."

    parts = [
        f"Agent difficulty summary ({label}):",
        (
            f"semantic_plans={summary.semantic_plan_count} "
            f"simulated_plans={summary.simulated_plan_count} "
            f"main_route_success_rate={summary.main_route_success_rate:.3f} "
            f"best_success_rate={summary.best_plan_success_rate:.3f} "
            f"main_route_difficulty={summary.main_route_difficulty:.3f} "
            f"segment_success_std={summary.segment_success_std:.3f} "
            f"dead_segment_ratio={summary.dead_segment_ratio:.3f} "
            f"dead_segments={summary.dead_segment_count}/{summary.unique_segment_count}"
        ),
        (
            f"target_weighted_final_stamina={breakdown.remaining_stamina_target:.3f} "
            f"weighted_final_stamina={breakdown.remaining_stamina_actual:.3f} "
            f"final_stamina_score={breakdown.remaining_stamina_score:.3f} "
            f"final_stamina_term={breakdown.remaining_stamina_term:.3f}"
        ),
    ]

    if not summary.plan_summaries:
        return "\n".join(parts)

    parts.append(
        "segment_success_rates_for_std="
        f"[{_format_segment_success_rates_for_std(summary.plan_summaries)}]"
    )
    parts.append(
        "dead_segment_analysis="
        f"[{_format_dead_segment_analysis(summary.plan_summaries)}]"
    )

    best_plan = max(
        summary.plan_summaries,
        key=lambda plan_summary: plan_summary.estimated_success_rate,
    )
    plan_kinds = _format_plan_route(best_plan.plan.steps)
    parts.append(
        f"best_plan={plan_kinds} estimated_success_rate={best_plan.estimated_success_rate:.3f}"
    )
    parts.append("plans:")

    for plan_index, plan_summary in enumerate(summary.plan_summaries):
        plan = plan_summary.plan
        route = _format_plan_route(plan.steps)
        status = "exact_solvable" if plan.semantic_success else "exact_dead"
        parts.append(
            f"plan={plan_index} status={status} "
            f"estimated_success_rate={plan_summary.estimated_success_rate:.3f} "
            f"route={route}"
        )

        if plan.shortest_cost is not None or plan.final_stamina is not None:
            parts.append(
                f"plan={plan_index} exact_shortest_cost={plan.shortest_cost} "
                f"exact_final_stamina={plan.final_stamina}"
            )

        if not plan_summary.segment_summaries:
            parts.append(f"plan={plan_index} no_agent_segments")
            continue

        for segment_index, segment in enumerate(plan_summary.segment_summaries):
            prefix = _format_plan_route(plan.steps[: segment_index + 1])
            segment_route = _format_segment_route(
                plan.steps[segment_index],
                plan.steps[segment_index + 1],
            )
            parts.append(
                f"plan={plan_index} segment={segment_index} "
                f"prefix={prefix} "
                f"move={segment_route} "
                f"success_rate={segment.success_rate:.3f} "
                f"success={segment.success_count}/{segment.agent_count} "
                f"avg_steps={segment.average_steps:.2f} "
                f"avg_revisits={segment.average_revisits:.2f} "
                f"avg_backtracks={segment.average_forced_backtracks:.2f} "
                f"avg_success_stamina={segment.average_success_remaining_stamina:.2f}"
            )

    return "\n".join(parts)


def _format_plan_route(steps) -> str:
    return " -> ".join(_format_step_label(step) for step in steps)


def _format_segment_route(source_step, target_step) -> str:
    return f"{_format_step_label(source_step)} -> {_format_step_label(target_step)}"


def _format_step_label(step) -> str:
    return f"{step.kind}@{step.position}"


def _format_segment_success_rates_for_std(plan_summaries) -> str:
    segment_rates_by_key = {}
    segment_labels_by_key = {}

    for plan_summary in plan_summaries:
        node_labels = {
            step.node_id: _format_step_label(step)
            for step in plan_summary.plan.steps
        }

        for segment in plan_summary.segment_summaries:
            segment_key = (segment.source_node_id, segment.target_node_id)
            segment_rates_by_key.setdefault(segment_key, []).append(segment.success_rate)
            segment_labels_by_key.setdefault(
                segment_key,
                (
                    f"{node_labels.get(segment.source_node_id, segment.source_position)}"
                    f" -> {node_labels.get(segment.target_node_id, segment.target_position)}"
                ),
            )

    formatted_segments = []

    for segment_key in sorted(segment_rates_by_key):
        segment_rates = segment_rates_by_key[segment_key]
        average_success_rate = sum(segment_rates) / len(segment_rates)
        occurrence_suffix = (
            f" occurrences={len(segment_rates)}"
            if len(segment_rates) > 1
            else ""
        )
        formatted_segments.append(
            f"{segment_labels_by_key[segment_key]}:{average_success_rate:.3f}{occurrence_suffix}"
        )

    return "; ".join(formatted_segments)


def _format_dead_segment_analysis(plan_summaries) -> str:
    segment_status_by_key = {}
    segment_labels_by_key = {}

    for plan_summary in plan_summaries:
        plan = plan_summary.plan
        node_labels = {
            step.node_id: _format_step_label(step)
            for step in plan.steps
        }

        for segment in plan_summary.segment_summaries:
            segment_key = (segment.source_node_id, segment.target_node_id)
            segment_status_by_key[segment_key] = "alive"
            segment_labels_by_key.setdefault(
                segment_key,
                (
                    f"{node_labels.get(segment.source_node_id, segment.source_position)}"
                    f" -> {node_labels.get(segment.target_node_id, segment.target_position)}"
                ),
            )

        if not plan.semantic_success and len(plan.steps) >= 2:
            source_step = plan.steps[-2]
            target_step = plan.steps[-1]
            segment_key = (source_step.node_id, target_step.node_id)

            if segment_status_by_key.get(segment_key) != "alive":
                segment_status_by_key[segment_key] = "dead"

            segment_labels_by_key.setdefault(
                segment_key,
                _format_segment_route(source_step, target_step),
            )

    formatted_segments = []

    for segment_key in sorted(segment_status_by_key):
        formatted_segments.append(
            f"{segment_status_by_key[segment_key]}:{segment_labels_by_key[segment_key]}"
        )

    return "; ".join(formatted_segments)


def get_solution_summary(state: BaselineState, label: str = "state") -> str:
    if GAME_MODE != "stamina_only":
        return f"Solution summary ({label}): not tracked for door_only mode."

    breakdown = stamina_aware_baseline_energy_breakdown(
        state=state,
        target_path_length=TARGET_PATH_LENGTH,
        target_remaining_stamina=TARGET_FINAL_STAMINA,
    )

    if not breakdown.solution_steps:
        return f"Solution summary ({label}): no successful stamina-only solution trace available."

    parts = [f"Solution summary ({label}):"]

    for step_index, step in enumerate(breakdown.solution_steps):
        parts.append(
            f"{step_index}. {step.kind}@{step.position} "
            f"edge_cost={step.edge_cost} stamina_after={step.remaining_stamina}"
        )

    return "\n".join(parts)


def find_shortest_path(grid: Grid, start: Position, goal: Position) -> list[Position] | None:
    if start == goal:
        return [start]

    queue: list[Position] = [start]
    parents: dict[Position, Position | None] = {start: None}

    while queue:
        row, col = queue.pop(0)

        for next_position in iter_neighbors(row, col):
            next_row, next_col = next_position

            if next_position in parents:
                continue

            if not is_walkable(grid, next_row, next_col):
                continue

            parents[next_position] = (row, col)

            if next_position == goal:
                path = [goal]
                current = goal

                while parents[current] is not None:
                    current = parents[current]
                    path.append(current)

                path.reverse()
                return path

            queue.append(next_position)

    return None


def choose_stamina_mode_door_position(grid: Grid, start: Position, max_path_length: int) -> Position:
    distances = bfs_distances(grid, start)
    candidate_positions = [
        position
        for position, distance in distances.items()
        if position != start and distance <= max_path_length
    ]

    if not candidate_positions:
        return choose_door_position(grid, start)

    return min(
        candidate_positions,
        key=lambda position: (abs(distances[position] - TARGET_PATH_LENGTH), -distances[position]),
    )


def construct_stamina_mode_items(
    path: list[Position],
    initial_stamina: int,
    item_kinds: tuple[str, ...],
) -> tuple[ItemPlacement, ...] | None:
    interior_positions = path[1:-1]

    if len(interior_positions) < len(item_kinds):
        return None

    stamina_kinds = [item_kind for item_kind in item_kinds if item_kind == "stamina"]
    key_kinds = [item_kind for item_kind in item_kinds if item_kind == "key"]
    path_end_index = len(path) - 1
    used_indices: set[int] = set()
    selected_positions: dict[int, ItemPlacement] = {}
    current_path_index = 0
    current_stamina = initial_stamina

    for stamina_offset, _ in enumerate(stamina_kinds):
        remaining_special_slots = len(stamina_kinds) - stamina_offset - 1 + len(key_kinds)
        max_reserved_index = path_end_index - 1 - remaining_special_slots
        furthest_reachable_index = min(path_end_index - 1, current_path_index + current_stamina)
        next_path_index = min(furthest_reachable_index, max_reserved_index)

        if next_path_index <= current_path_index:
            return None

        selected_positions[next_path_index] = ItemPlacement(
            kind="stamina",
            position=path[next_path_index],
            value=get_default_item_value("stamina"),
        )
        used_indices.add(next_path_index)
        current_stamina = (
            current_stamina
            - (next_path_index - current_path_index)
            + get_default_item_value("stamina")
        )
        current_path_index = next_path_index

    for key_kind in key_kinds:
        preferred_index = max(1, min(path_end_index - 1, path_end_index // 2))
        candidate_indices = [
            index
            for index in range(preferred_index, path_end_index)
            if index not in used_indices
        ] + [
            index
            for index in range(1, preferred_index)
            if index not in used_indices
        ]

        if not candidate_indices:
            return None

        key_index = candidate_indices[0]
        selected_positions[key_index] = ItemPlacement(
            kind=key_kind,
            position=path[key_index],
            value=get_default_item_value(key_kind),
        )
        used_indices.add(key_index)

    return tuple(
        selected_positions[index]
        for index in sorted(selected_positions)
    )


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
        max_path_length = mode_config.initial_stamina + sum(
            get_default_item_value(item_kind)
            for item_kind in mode_config.item_kinds
            if item_kind == "stamina"
        )
        door = (
            choose_stamina_mode_door_position(grid, START_POS, max_path_length)
            if mode_config.uses_stamina_solver
            else choose_door_position(grid, START_POS)
        )

        if mode_config.uses_stamina_solver:
            path = find_shortest_path(grid, START_POS, door)

            if path is None:
                continue

            items = construct_stamina_mode_items(
                path=path,
                initial_stamina=mode_config.initial_stamina,
                item_kinds=mode_config.item_kinds,
            )

            if items is None:
                continue

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
            continue

        for _ in range(MAX_ITEM_PLACEMENT_ATTEMPTS):
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


def pick_random_door_destination(state: BaselineState) -> Position | None:
    blocked_positions = get_protected_positions(state) - {state.door}
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


def propose_door_move(state: BaselineState) -> BaselineState | None:
    destination = pick_random_door_destination(state)

    if destination is None or destination == state.door:
        return None

    candidate_state = BaselineState(
        grid=state.grid,
        start=state.start,
        door=destination,
        items=state.items,
        initial_stamina=state.initial_stamina,
        locked_door=state.locked_door,
    )
    return candidate_state if is_state_valid(candidate_state) else None


def try_propose_candidate(state: BaselineState) -> BaselineState | None:
    mode_config = get_mode_config()
    move_type = random.choice(mode_config.proposal_move_types)

    if move_type == "topology":
        return propose_topology_move(state)

    if move_type == "item_move":
        return propose_item_move(state)

    if move_type == "door_move":
        return propose_door_move(state)

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
    print(get_energy_breakdown(current_state))
    print(get_solution_summary(current_state, label="initial"))
    print(get_agent_difficulty_summary(current_state, label="initial"))
    print(f"Mode: {mode_config.name}")
    print(f"Stamina energy model: {STAMINA_ENERGY_MODEL}")
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
        energy_function=get_energy_function(),
    )

    print("\n[Final state]")
    print(render_ascii_map(final_state))
    print(f"Final energy: {final_energy}")
    print(get_energy_breakdown(final_state))
    print(get_solution_summary(final_state, label="final"))
    print(get_agent_difficulty_summary(final_state, label="final"))
    print(f"Final door position: {final_state.door}")
    print("\n[Best state visited]")
    print(render_ascii_map(best_state))
    print(f"Best energy: {best_energy}")
    print(get_energy_breakdown(best_state))
    print(get_solution_summary(best_state, label="best"))
    print(get_agent_difficulty_summary(best_state, label="best"))
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
