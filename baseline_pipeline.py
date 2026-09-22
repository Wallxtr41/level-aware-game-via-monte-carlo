from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Callable

from utils import game_config
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
from utils.map_analysis import (
    bfs_distances,
    bfs_distances_with_blocked,
    copy_grid,
    is_walkable,
    iter_neighbors,
)
from utils.map_entities import (
    get_default_item_value,
    ItemPlacement,
    choose_door_position,
    get_walkable_positions,
    place_items,
)
from utils.maze_generation import generate_maze_map

RANDOM_SEED = 42 #5

GRID_WIDTH = game_config.GRID_WIDTH
GRID_HEIGHT = game_config.GRID_HEIGHT
START_POS = (1, 1)
TARGET_PATH_LENGTH = 52
TARGET_FINAL_STAMINA = 10
TARGET_AGENT_DIFFICULTY = game_config.TARGET_AGENT_DIFFICULTY
AGENT_DIFFICULTY_WEIGHT = 30.0
SEGMENT_TARGET_WEIGHT = 8.0
SEGMENT_BALANCE_WEIGHT = 0
DEAD_SEGMENT_WEIGHT = 0
STAMINA_USAGE_WEIGHT = 15.0
TARGET_STAMINA_USAGE_RATE = None  # None => TARGET_AGENT_DIFFICULTY
FINAL_STAMINA_WEIGHT = 6.0
FINAL_STAMINA_TARGET_FACTOR = 0.8
SPACING_WEIGHT = 8.0
SPACING_TARGET_SCALE = 1.3
COVERAGE_WEIGHT = 10.0
COVERAGE_TARGET_BASE = 0.15
COVERAGE_TARGET_DIFFICULTY_SCALE = 0.55
BRANCHING_WEIGHT = 10.0
BRANCHING_TARGET_BASE = 0.25
BRANCHING_TARGET_DIFFICULTY_SCALE = 0.5
INITIAL_STAMINA_BASE_SCALE = 1.5
INITIAL_STAMINA_DIFFICULTY_SCALE = 2
INITIAL_STAMINA_NOISE_STD_SCALE = 0.2
MIN_INITIAL_STAMINA_SCALE = 1.0
MAX_INITIAL_STAMINA_SCALE = 4.0
AGENTS_PER_SEGMENT = 30
AGENT_DIFFICULTY_SEED = 12345
MAX_INITIAL_STATE_ATTEMPTS = 200
MAX_ITEM_PLACEMENT_ATTEMPTS = 100
INITIAL_DOOR_CANDIDATE_LIMIT = 8
INITIAL_ITEM_CANDIDATE_LIMIT = 8
INITIAL_VALID_CANDIDATE_LIMIT = 120
INITIAL_EARLY_STOP_ENERGY = 1.0
INITIAL_ITEM_MIN_START_DISTANCE_SCALE = 0.25
DOOR_REQUIRES_KEY = game_config.DOOR_REQUIRES_KEY
STAMINA_ITEM_COUNT = game_config.STAMINA_ITEM_COUNT
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
    segment_target_weight=SEGMENT_TARGET_WEIGHT,
    segment_balance_weight=SEGMENT_BALANCE_WEIGHT,
    dead_segment_weight=DEAD_SEGMENT_WEIGHT,
    stamina_usage_weight=STAMINA_USAGE_WEIGHT,
    target_stamina_usage_rate=TARGET_STAMINA_USAGE_RATE,
    final_stamina_weight=FINAL_STAMINA_WEIGHT,
    final_stamina_target_factor=FINAL_STAMINA_TARGET_FACTOR,
    spacing_weight=SPACING_WEIGHT,
    spacing_target_scale=SPACING_TARGET_SCALE,
    coverage_weight=COVERAGE_WEIGHT,
    coverage_target_base=COVERAGE_TARGET_BASE,
    coverage_target_difficulty_scale=COVERAGE_TARGET_DIFFICULTY_SCALE,
    branching_weight=BRANCHING_WEIGHT,
    branching_target_base=BRANCHING_TARGET_BASE,
    branching_target_difficulty_scale=BRANCHING_TARGET_DIFFICULTY_SCALE,
    agent_config=AGENT_DIFFICULTY_CONFIG,
)


@dataclass(frozen=True)
class ModeConfig:
    name: str
    uses_stamina_solver: bool
    initial_stamina: int | None
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
        initial_stamina=None,
        locked_door=DOOR_REQUIRES_KEY,
        item_kinds=game_config.build_stamina_item_kinds(),
        proposal_move_types=("topology", "item_move", "door_move"),
    ),
}


def rebuild_runtime_config() -> None:
    global AGENT_DIFFICULTY_CONFIG
    global STAMINA_ONLY_ENERGY_FUNCTION
    global STAMINA_AGENT_DIFFICULTY_ENERGY_FUNCTION
    global MODE_CONFIGS

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
        segment_target_weight=SEGMENT_TARGET_WEIGHT,
        segment_balance_weight=SEGMENT_BALANCE_WEIGHT,
        dead_segment_weight=DEAD_SEGMENT_WEIGHT,
        stamina_usage_weight=STAMINA_USAGE_WEIGHT,
        target_stamina_usage_rate=TARGET_STAMINA_USAGE_RATE,
        final_stamina_weight=FINAL_STAMINA_WEIGHT,
        final_stamina_target_factor=FINAL_STAMINA_TARGET_FACTOR,
        spacing_weight=SPACING_WEIGHT,
        spacing_target_scale=SPACING_TARGET_SCALE,
        coverage_weight=COVERAGE_WEIGHT,
        coverage_target_base=COVERAGE_TARGET_BASE,
        coverage_target_difficulty_scale=COVERAGE_TARGET_DIFFICULTY_SCALE,
        branching_weight=BRANCHING_WEIGHT,
        branching_target_base=BRANCHING_TARGET_BASE,
        branching_target_difficulty_scale=BRANCHING_TARGET_DIFFICULTY_SCALE,
        agent_config=AGENT_DIFFICULTY_CONFIG,
    )
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
            initial_stamina=None,
            locked_door=DOOR_REQUIRES_KEY,
            item_kinds=game_config.build_stamina_item_kinds(),
            proposal_move_types=("topology", "item_move", "door_move"),
        ),
    }
    HC3_CACHE.graphs.clear()


def apply_difficulty_stamina_config(
    config: game_config.DifficultyStaminaConfig,
) -> game_config.DifficultyStaminaConfig:
    global GRID_WIDTH
    global GRID_HEIGHT
    global TARGET_AGENT_DIFFICULTY
    global DOOR_REQUIRES_KEY
    global STAMINA_ITEM_COUNT
    global GAME_MODE
    global STAMINA_ENERGY_MODEL

    config = game_config.apply_difficulty_stamina_config(config)
    GRID_WIDTH = config.grid_width
    GRID_HEIGHT = config.grid_height
    TARGET_AGENT_DIFFICULTY = config.target_agent_difficulty
    DOOR_REQUIRES_KEY = config.door_requires_key
    STAMINA_ITEM_COUNT = config.stamina_item_count
    GAME_MODE = "stamina_only"
    STAMINA_ENERGY_MODEL = "agent_difficulty"
    rebuild_runtime_config()
    return config


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


def resolve_initial_stamina(mode_config: ModeConfig) -> int:
    if mode_config.initial_stamina is not None:
        return mode_config.initial_stamina

    if not mode_config.uses_stamina_solver:
        return 0

    return calculate_auto_initial_stamina(
        grid_width=GRID_WIDTH,
        grid_height=GRID_HEIGHT,
        target_agent_difficulty=TARGET_AGENT_DIFFICULTY,
        rng=random,
    )


def calculate_auto_initial_stamina(
    *,
    grid_width: int,
    grid_height: int,
    target_agent_difficulty: float,
    rng,
) -> int:
    grid_scale = math.sqrt(max(1, grid_width * grid_height))
    difficulty = min(1.0, max(0.0, target_agent_difficulty))
    mean_stamina = grid_scale * (
        INITIAL_STAMINA_BASE_SCALE
        + INITIAL_STAMINA_DIFFICULTY_SCALE * difficulty
    )
    std_stamina = grid_scale * INITIAL_STAMINA_NOISE_STD_SCALE
    sampled_stamina = (
        rng.gauss(mean_stamina, std_stamina)
        if std_stamina > 0
        else mean_stamina
    )
    min_stamina = grid_scale * MIN_INITIAL_STAMINA_SCALE
    max_stamina = grid_scale * MAX_INITIAL_STAMINA_SCALE
    clamped_stamina = min(max_stamina, max(min_stamina, sampled_stamina))
    return max(1, round(clamped_stamina))


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
                segment_target_weight=SEGMENT_TARGET_WEIGHT,
                segment_balance_weight=SEGMENT_BALANCE_WEIGHT,
                dead_segment_weight=DEAD_SEGMENT_WEIGHT,
                stamina_usage_weight=STAMINA_USAGE_WEIGHT,
                target_stamina_usage_rate=TARGET_STAMINA_USAGE_RATE,
                final_stamina_weight=FINAL_STAMINA_WEIGHT,
                final_stamina_target_factor=FINAL_STAMINA_TARGET_FACTOR,
                spacing_weight=SPACING_WEIGHT,
                spacing_target_scale=SPACING_TARGET_SCALE,
                coverage_weight=COVERAGE_WEIGHT,
                coverage_target_base=COVERAGE_TARGET_BASE,
                coverage_target_difficulty_scale=COVERAGE_TARGET_DIFFICULTY_SCALE,
                branching_weight=BRANCHING_WEIGHT,
                branching_target_base=BRANCHING_TARGET_BASE,
                branching_target_difficulty_scale=BRANCHING_TARGET_DIFFICULTY_SCALE,
                agent_config=AGENT_DIFFICULTY_CONFIG,
            )
            return (
                f"target_agent_difficulty={breakdown.agent_difficulty_target} "
                f"main_route_difficulty={breakdown.agent_difficulty_actual} "
                f"main_route_success_rate={breakdown.agent_success_rate} "
                f"main_route_term={breakdown.agent_difficulty_term} "
                f"segment_success_target={breakdown.segment_success_target} "
                f"segment_target_score={breakdown.segment_target_score} "
                f"segment_target_term={breakdown.segment_target_term} "
                f"segment_success_std={breakdown.segment_balance_penalty} "
                f"segment_balance_score={breakdown.segment_balance_score} "
                f"segment_balance_term={breakdown.segment_balance_term} "
                f"dead_segment_ratio={breakdown.dead_segment_ratio} "
                f"dead_segment_term={breakdown.dead_segment_term} "
                f"stamina_usage_target={breakdown.stamina_usage_target} "
                f"stamina_usage_actual={breakdown.stamina_usage_actual} "
                f"stamina_usage_score={breakdown.stamina_usage_score} "
                f"stamina_usage_term={breakdown.stamina_usage_term} "
                f"target_weighted_final_stamina={breakdown.remaining_stamina_target} "
                f"weighted_final_stamina={breakdown.remaining_stamina_actual} "
                f"final_stamina_score={breakdown.remaining_stamina_score} "
                f"final_stamina_term={breakdown.remaining_stamina_term} "
                f"spacing_target={breakdown.spacing_target} "
                f"spacing_actual={breakdown.spacing_actual} "
                f"spacing_score={breakdown.spacing_score} "
                f"spacing_term={breakdown.spacing_term} "
                f"coverage_target={breakdown.coverage_target} "
                f"coverage_actual={breakdown.coverage_actual} "
                f"coverage_term={breakdown.coverage_term} "
                f"branching_target={breakdown.branching_target} "
                f"branching_actual={breakdown.branching_actual} "
                f"junction_density={breakdown.junction_density} "
                f"trap_depth_score={breakdown.trap_depth_score} "
                f"branching_term={breakdown.branching_term} "
                f"total={breakdown.total_energy}\n"
                "terms: "
                f"main_route={breakdown.agent_difficulty_term} "
                f"segment_target={breakdown.segment_target_term} "
                f"segment_balance={breakdown.segment_balance_term} "
                f"dead_segment={breakdown.dead_segment_term} "
                f"stamina_usage={breakdown.stamina_usage_term} "
                f"final_stamina={breakdown.remaining_stamina_term} "
                f"spacing={breakdown.spacing_term} "
                f"coverage={breakdown.coverage_term} "
                f"branching={breakdown.branching_term} "
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
        segment_target_weight=SEGMENT_TARGET_WEIGHT,
        segment_balance_weight=SEGMENT_BALANCE_WEIGHT,
        dead_segment_weight=DEAD_SEGMENT_WEIGHT,
        stamina_usage_weight=STAMINA_USAGE_WEIGHT,
        target_stamina_usage_rate=TARGET_STAMINA_USAGE_RATE,
        final_stamina_weight=FINAL_STAMINA_WEIGHT,
        final_stamina_target_factor=FINAL_STAMINA_TARGET_FACTOR,
        spacing_weight=SPACING_WEIGHT,
        spacing_target_scale=SPACING_TARGET_SCALE,
        coverage_weight=COVERAGE_WEIGHT,
        coverage_target_base=COVERAGE_TARGET_BASE,
        coverage_target_difficulty_scale=COVERAGE_TARGET_DIFFICULTY_SCALE,
        branching_weight=BRANCHING_WEIGHT,
        branching_target_base=BRANCHING_TARGET_BASE,
        branching_target_difficulty_scale=BRANCHING_TARGET_DIFFICULTY_SCALE,
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
            f"effective_success_rate={breakdown.effective_success_rate:.3f} "
            f"effective_difficulty={breakdown.agent_difficulty_actual:.3f} "
            f"best_success_rate={summary.best_plan_success_rate:.3f} "
            f"main_route_difficulty={summary.main_route_difficulty:.3f} "
            f"segment_success_target={breakdown.segment_success_target:.3f} "
            f"segment_target_score={breakdown.segment_target_score:.3f} "
            f"segment_success_std={summary.segment_success_std:.3f} "
            f"dead_segment_ratio={summary.dead_segment_ratio:.3f} "
            f"dead_segments={summary.dead_segment_count}/{summary.unique_segment_count}"
        ),
        (
            f"stamina_usage_target={breakdown.stamina_usage_target:.3f} "
            f"stamina_usage_actual={breakdown.stamina_usage_actual:.3f} "
            f"stamina_usage_score={breakdown.stamina_usage_score:.3f} "
            f"stamina_usage_term={breakdown.stamina_usage_term:.3f}"
        ),
        (
            f"target_weighted_final_stamina={breakdown.remaining_stamina_target:.3f} "
            f"weighted_final_stamina={breakdown.remaining_stamina_actual:.3f} "
            f"final_stamina_score={breakdown.remaining_stamina_score:.3f} "
            f"final_stamina_term={breakdown.remaining_stamina_term:.3f}"
        ),
        (
            f"spacing_target={breakdown.spacing_target:.3f} "
            f"spacing_actual={breakdown.spacing_actual:.3f} "
            f"spacing_score={breakdown.spacing_score:.3f} "
            f"spacing_term={breakdown.spacing_term:.3f}"
        ),
        (
            f"coverage_target={breakdown.coverage_target:.3f} "
            f"coverage_actual={breakdown.coverage_actual:.3f} "
            f"coverage_term={breakdown.coverage_term:.3f}"
        ),
        (
            f"branching_target={breakdown.branching_target:.3f} "
            f"branching_actual={breakdown.branching_actual:.3f} "
            f"junction_density={breakdown.junction_density:.3f} "
            f"trap_depth_score={breakdown.trap_depth_score:.3f} "
            f"branching_term={breakdown.branching_term:.3f}"
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
    candidates = choose_stamina_mode_door_candidates(
        grid=grid,
        start=start,
        max_path_length=max_path_length,
        initial_stamina=None,
        item_kinds=(),
        limit=1,
    )

    if candidates:
        return candidates[0]

    return choose_door_position(grid, start)


def choose_stamina_mode_door_candidates(
    *,
    grid: Grid,
    start: Position,
    max_path_length: int,
    initial_stamina: int | None,
    item_kinds: tuple[str, ...],
    limit: int,
) -> list[Position]:
    distances = bfs_distances(grid, start)
    candidate_positions = [
        position
        for position, distance in distances.items()
        if position != start and distance <= max_path_length
        and is_door_non_partitioning(grid, start, position)
    ]

    if not candidate_positions:
        fallback_positions = [
            position
            for position in distances
            if position != start and is_door_non_partitioning(grid, start, position)
        ]
        return fallback_positions[:1]

    path_target = _initial_path_target(
        max_path_length=max_path_length,
        initial_stamina=initial_stamina,
        item_kinds=item_kinds,
    )
    target_sorted_candidates = sorted(
        candidate_positions,
        key=lambda position: (
            abs(distances[position] - path_target),
            -distances[position],
            position,
        ),
    )
    distance_sorted_candidates = sorted(
        candidate_positions,
        key=lambda position: (distances[position], position),
    )
    mixed_candidates: list[Position] = []

    def add_positions(positions: list[Position]) -> None:
        for position in positions:
            if len(mixed_candidates) >= limit:
                return

            if position in mixed_candidates:
                continue

            mixed_candidates.append(position)

            if len(mixed_candidates) >= limit:
                return

    difficulty = min(1.0, max(0.0, TARGET_AGENT_DIFFICULTY))
    near_count = 3 if difficulty <= 0.35 else 1
    far_count = 3 if difficulty >= 0.65 else 1
    target_count = max(1, limit - near_count - far_count)

    add_positions(distance_sorted_candidates[:near_count])
    add_positions(target_sorted_candidates[:target_count])
    add_positions(list(reversed(distance_sorted_candidates[-far_count:])))

    if len(mixed_candidates) < limit:
        add_positions(target_sorted_candidates)

    return mixed_candidates


def _initial_spacing_target() -> float:
    grid_scale = math.sqrt(max(1, GRID_WIDTH * GRID_HEIGHT))
    difficulty_scale = 0.5 + (0.5 * TARGET_AGENT_DIFFICULTY)
    return SPACING_TARGET_SCALE * grid_scale * difficulty_scale


def _initial_path_target(
    *,
    max_path_length: int,
    initial_stamina: int | None,
    item_kinds: tuple[str, ...],
) -> float:
    if STAMINA_ENERGY_MODEL != "agent_difficulty" or initial_stamina is None:
        return min(max_path_length, TARGET_PATH_LENGTH)

    stamina_value_budget = sum(
        get_default_item_value(item_kind)
        for item_kind in item_kinds
        if item_kind == "stamina"
    )
    stamina_usage_target = _target_stamina_usage_for_initial(item_kinds)
    expected_stamina_budget = initial_stamina + (stamina_value_budget * stamina_usage_target)
    target_final_stamina = (
        FINAL_STAMINA_TARGET_FACTOR
        * initial_stamina
        * (1.0 - TARGET_AGENT_DIFFICULTY)
    )
    stamina_path_target = max(1.0, expected_stamina_budget - target_final_stamina)
    key_count = sum(1 for item_kind in item_kinds if item_kind == "key")
    spacing_path_target = _initial_spacing_target() * (2.0 if key_count else 1.0)
    return min(max_path_length, max(stamina_path_target, spacing_path_target))


def _target_stamina_usage_for_initial(item_kinds: tuple[str, ...]) -> float:
    stamina_count = sum(1 for item_kind in item_kinds if item_kind == "stamina")

    if stamina_count == 0:
        return 0.0

    explicit_target = TARGET_STAMINA_USAGE_RATE
    stamina_usage_target = TARGET_AGENT_DIFFICULTY if explicit_target is None else explicit_target
    return min(1.0, max(0.0, stamina_usage_target))


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


def construct_stamina_mode_item_candidates(
    *,
    grid: Grid,
    path: list[Position],
    initial_stamina: int,
    item_kinds: tuple[str, ...],
    rng,
) -> list[tuple[ItemPlacement, ...]]:
    candidates: list[tuple[ItemPlacement, ...]] = []
    seen_keys: set[tuple[tuple[str, Position], ...]] = set()
    start_distances = bfs_distances(grid, path[0])
    minimum_start_distances = _initial_item_start_distance_fallbacks(
        _initial_min_item_start_distance(grid)
    )

    def add_candidate(
        candidate: tuple[ItemPlacement, ...] | None,
        *,
        minimum_start_distance: int,
    ) -> None:
        if candidate is None:
            return

        if len(candidate) != len(item_kinds):
            return

        positions = [item.position for item in candidate]

        if len(set(positions)) != len(positions):
            return

        if any(position in {path[0], path[-1]} for position in positions):
            return

        if any(
            start_distances.get(position, 0) < minimum_start_distance
            for position in positions
        ):
            return

        candidate_key = tuple((item.kind, item.position) for item in candidate)

        if candidate_key in seen_keys:
            return

        seen_keys.add(candidate_key)
        candidates.append(candidate)

    def generate_candidates(minimum_start_distance: int) -> None:
        add_candidate(
            construct_balanced_path_items(
                path=path,
                item_kinds=item_kinds,
                stamina_on_path_count=sum(1 for item_kind in item_kinds if item_kind == "stamina"),
            ),
            minimum_start_distance=minimum_start_distance,
        )
        add_candidate(
            construct_balanced_path_items(
                path=path,
                item_kinds=item_kinds,
                stamina_on_path_count=_target_on_path_stamina_count(item_kinds),
            ),
            minimum_start_distance=minimum_start_distance,
        )
        add_candidate(
            construct_mixed_path_branch_items(
                grid=grid,
                path=path,
                item_kinds=item_kinds,
                stamina_on_path_count=_target_on_path_stamina_count(item_kinds),
            ),
            minimum_start_distance=minimum_start_distance,
        )
        add_candidate(
            construct_stamina_mode_items(
                path=path,
                initial_stamina=initial_stamina,
                item_kinds=item_kinds,
            ),
            minimum_start_distance=minimum_start_distance,
        )

        random_attempts = 0
        max_random_attempts = INITIAL_ITEM_CANDIDATE_LIMIT * 8

        while len(candidates) < INITIAL_ITEM_CANDIDATE_LIMIT and random_attempts < max_random_attempts:
            randomized_candidate = construct_randomized_path_items(
                grid=grid,
                path=path,
                item_kinds=item_kinds,
                rng=rng,
            )

            if randomized_candidate is None:
                break

            add_candidate(
                randomized_candidate,
                minimum_start_distance=minimum_start_distance,
            )
            random_attempts += 1

    for minimum_start_distance in minimum_start_distances:
        generate_candidates(minimum_start_distance)

        if candidates:
            break

    return candidates[:INITIAL_ITEM_CANDIDATE_LIMIT]


def construct_balanced_path_items(
    *,
    path: list[Position],
    item_kinds: tuple[str, ...],
    stamina_on_path_count: int,
) -> tuple[ItemPlacement, ...] | None:
    path_end_index = len(path) - 1

    if path_end_index <= len(item_kinds):
        return None

    stamina_count = sum(1 for item_kind in item_kinds if item_kind == "stamina")
    key_count = sum(1 for item_kind in item_kinds if item_kind == "key")
    stamina_on_path_count = min(stamina_count, max(0, stamina_on_path_count))
    used_indices: set[int] = set()
    positions_by_kind: dict[str, list[Position]] = {"stamina": [], "key": []}

    if key_count:
        key_indices = _spread_indices(
            start_index=1,
            end_index=path_end_index - 1,
            count=key_count,
        )
        positions_by_kind["key"].extend(path[index] for index in key_indices)
        used_indices.update(key_indices)

    if stamina_on_path_count:
        stamina_indices = _spread_available_indices(
            start_index=1,
            end_index=path_end_index - 1,
            count=stamina_on_path_count,
            used_indices=used_indices,
        )
        positions_by_kind["stamina"].extend(path[index] for index in stamina_indices)
        used_indices.update(stamina_indices)

    off_path_stamina_count = stamina_count - stamina_on_path_count

    if off_path_stamina_count:
        return None

    return _build_items_from_positions(item_kinds=item_kinds, positions_by_kind=positions_by_kind)


def construct_mixed_path_branch_items(
    *,
    grid: Grid,
    path: list[Position],
    item_kinds: tuple[str, ...],
    stamina_on_path_count: int,
) -> tuple[ItemPlacement, ...] | None:
    path_candidate = construct_balanced_path_items(
        path=path,
        item_kinds=tuple(
            item_kind
            for item_kind in item_kinds
            if item_kind != "stamina"
        )
        + tuple("stamina" for _ in range(stamina_on_path_count)),
        stamina_on_path_count=stamina_on_path_count,
    )

    if path_candidate is None:
        return None

    stamina_count = sum(1 for item_kind in item_kinds if item_kind == "stamina")
    off_path_stamina_count = stamina_count - stamina_on_path_count
    positions_by_kind: dict[str, list[Position]] = {"stamina": [], "key": []}

    for item in path_candidate:
        positions_by_kind.setdefault(item.kind, []).append(item.position)

    if off_path_stamina_count:
        blocked_positions = {path[0], path[-1], *(item.position for item in path_candidate)}
        off_path_positions = choose_spread_off_path_positions(
            grid=grid,
            path=path,
            blocked_positions=blocked_positions,
            count=off_path_stamina_count,
        )

        if len(off_path_positions) < off_path_stamina_count:
            return None

        positions_by_kind["stamina"].extend(off_path_positions)

    return _build_items_from_positions(item_kinds=item_kinds, positions_by_kind=positions_by_kind)


def construct_randomized_path_items(
    *,
    grid: Grid,
    path: list[Position],
    item_kinds: tuple[str, ...],
    rng,
) -> tuple[ItemPlacement, ...] | None:
    interior_positions = path[1:-1]

    if len(interior_positions) < len(item_kinds):
        return None

    stamina_count = sum(1 for item_kind in item_kinds if item_kind == "stamina")
    key_count = sum(1 for item_kind in item_kinds if item_kind == "key")
    on_path_stamina_count = rng.randint(0, stamina_count) if stamina_count else 0
    used_positions: set[Position] = set()
    positions_by_kind: dict[str, list[Position]] = {"stamina": [], "key": []}

    key_sample_pool = interior_positions[:]
    rng.shuffle(key_sample_pool)
    key_positions = key_sample_pool[:key_count]
    positions_by_kind["key"].extend(key_positions)
    used_positions.update(key_positions)

    path_stamina_pool = [
        position
        for position in interior_positions
        if position not in used_positions
    ]
    rng.shuffle(path_stamina_pool)
    path_stamina_positions = path_stamina_pool[:on_path_stamina_count]
    positions_by_kind["stamina"].extend(path_stamina_positions)
    used_positions.update(path_stamina_positions)

    off_path_stamina_count = stamina_count - len(path_stamina_positions)

    if off_path_stamina_count:
        off_path_positions = choose_spread_off_path_positions(
            grid=grid,
            path=path,
            blocked_positions={path[0], path[-1], *used_positions},
            count=off_path_stamina_count,
        )

        if len(off_path_positions) < off_path_stamina_count:
            return None

        positions_by_kind["stamina"].extend(off_path_positions)

    return _build_items_from_positions(item_kinds=item_kinds, positions_by_kind=positions_by_kind)


def choose_spread_off_path_positions(
    *,
    grid: Grid,
    path: list[Position],
    blocked_positions: set[Position],
    count: int,
) -> list[Position]:
    path_positions = set(path)
    candidate_positions = [
        position
        for position in get_walkable_positions(grid, blocked_positions=blocked_positions)
        if position not in path_positions
    ]
    selected_positions: list[Position] = []

    while candidate_positions and len(selected_positions) < count:
        best_position = max(
            candidate_positions,
            key=lambda position: (
                _min_manhattan_distance(position, [*path, *selected_positions]),
                position,
            ),
        )
        selected_positions.append(best_position)
        candidate_positions.remove(best_position)

    return selected_positions


def _target_on_path_stamina_count(item_kinds: tuple[str, ...]) -> int:
    stamina_count = sum(1 for item_kind in item_kinds if item_kind == "stamina")

    if stamina_count == 0:
        return 0

    stamina_usage_target = _target_stamina_usage_for_initial(item_kinds)
    target_count = math.floor((stamina_count * stamina_usage_target) + 0.5)
    return min(stamina_count, max(0, target_count))


def _initial_min_item_start_distance(grid: Grid) -> int:
    grid_scale = math.sqrt(max(1, len(grid) * (len(grid[0]) if grid else 0)))
    return max(2, round(grid_scale * INITIAL_ITEM_MIN_START_DISTANCE_SCALE))


def _initial_item_start_distance_fallbacks(minimum_distance: int) -> tuple[int, ...]:
    relaxed_distance = max(2, minimum_distance // 2)
    fallback_distances = (minimum_distance, relaxed_distance, 1)
    unique_distances: list[int] = []

    for distance in fallback_distances:
        if distance not in unique_distances:
            unique_distances.append(distance)

    return tuple(unique_distances)


def _spread_indices(start_index: int, end_index: int, count: int) -> list[int]:
    if count <= 0:
        return []

    if end_index < start_index:
        return []

    span = end_index - start_index + 1
    return [
        start_index + min(span - 1, max(0, round(((index + 1) * span / (count + 1)) - 1)))
        for index in range(count)
    ]


def _spread_available_indices(
    *,
    start_index: int,
    end_index: int,
    count: int,
    used_indices: set[int],
) -> list[int]:
    available_indices = [
        index
        for index in range(start_index, end_index + 1)
        if index not in used_indices
    ]

    if len(available_indices) < count:
        return []

    return [
        available_indices[
            min(
                len(available_indices) - 1,
                max(0, round(((index + 1) * len(available_indices) / (count + 1)) - 1)),
            )
        ]
        for index in range(count)
    ]


def _build_items_from_positions(
    *,
    item_kinds: tuple[str, ...],
    positions_by_kind: dict[str, list[Position]],
) -> tuple[ItemPlacement, ...] | None:
    remaining_positions_by_kind = {
        item_kind: positions[:]
        for item_kind, positions in positions_by_kind.items()
    }
    placements: list[ItemPlacement] = []

    for item_kind in item_kinds:
        item_positions = remaining_positions_by_kind.get(item_kind, [])

        if not item_positions:
            return None

        position = item_positions.pop(0)
        placements.append(
            ItemPlacement(
                kind=item_kind,
                position=position,
                value=get_default_item_value(item_kind),
            )
        )

    return tuple(placements)


def _min_manhattan_distance(position: Position, other_positions: list[Position]) -> int:
    if not other_positions:
        return 0

    return min(
        abs(position[0] - other_position[0]) + abs(position[1] - other_position[1])
        for other_position in other_positions
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


def is_door_non_partitioning(grid: Grid, start: Position, door: Position) -> bool:
    if start == door:
        return False

    start_row, start_col = start
    door_row, door_col = door

    if not is_walkable(grid, start_row, start_col):
        return False

    if not is_walkable(grid, door_row, door_col):
        return False

    reachable_without_door = bfs_distances_with_blocked(
        grid,
        start,
        blocked_positions={door},
    )
    walkable_without_door_count = sum(
        1
        for row_index, row in enumerate(grid)
        for col_index, cell in enumerate(row)
        if cell == 0 and (row_index, col_index) != door
    )
    return len(reachable_without_door) == walkable_without_door_count


def is_state_valid(state: BaselineState) -> bool:
    mode_config = get_mode_config()
    start_row, start_col = state.start
    door_row, door_col = state.door

    if not is_walkable(state.grid, start_row, start_col):
        return False

    if not is_walkable(state.grid, door_row, door_col):
        return False

    if not is_door_non_partitioning(state.grid, state.start, state.door):
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
    initial_stamina = resolve_initial_stamina(mode_config)
    energy_function = get_energy_function()
    best_state: BaselineState | None = None
    best_energy = math.inf
    valid_candidate_count = 0

    for _ in range(MAX_INITIAL_STATE_ATTEMPTS):
        grid = generate_maze_map(GRID_WIDTH, GRID_HEIGHT)

        if mode_config.uses_stamina_solver:
            max_path_length = initial_stamina + sum(
                get_default_item_value(item_kind)
                for item_kind in mode_config.item_kinds
                if item_kind == "stamina"
            )
            door_candidates = choose_stamina_mode_door_candidates(
                grid=grid,
                start=START_POS,
                max_path_length=max_path_length,
                initial_stamina=initial_stamina,
                item_kinds=mode_config.item_kinds,
                limit=INITIAL_DOOR_CANDIDATE_LIMIT,
            )

            for door in door_candidates:
                path = find_shortest_path(grid, START_POS, door)

                if path is None:
                    continue

                item_candidates = construct_stamina_mode_item_candidates(
                    grid=grid,
                    path=path,
                    initial_stamina=initial_stamina,
                    item_kinds=mode_config.item_kinds,
                    rng=random,
                )

                for items in item_candidates:
                    state = BaselineState(
                        grid=grid,
                        start=START_POS,
                        door=door,
                        items=items,
                        initial_stamina=initial_stamina,
                        locked_door=mode_config.locked_door,
                    )

                    if not is_state_valid(state):
                        continue

                    valid_candidate_count += 1
                    candidate_energy = energy_function(state)

                    if candidate_energy < best_energy:
                        best_energy = candidate_energy
                        best_state = state

                    if candidate_energy <= INITIAL_EARLY_STOP_ENERGY:
                        return state

                    if valid_candidate_count >= INITIAL_VALID_CANDIDATE_LIMIT:
                        return best_state
            continue

        door = choose_door_position(grid, START_POS)

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
                initial_stamina=initial_stamina,
                locked_door=mode_config.locked_door,
            )

            if is_state_valid(state):
                return state

    if best_state is not None:
        return best_state

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
    walkable_positions = [
        position
        for position in get_walkable_positions(state.grid, blocked_positions=blocked_positions)
        if is_door_non_partitioning(state.grid, state.start, position)
    ]

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
