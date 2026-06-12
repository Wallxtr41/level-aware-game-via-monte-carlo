from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Protocol

from utils.agent_difficulty import (
    AgentDifficultyConfig,
    AgentDifficultySummary,
    estimate_agent_difficulty,
)
from utils.hard_constraints import (
    StaminaOnlyHC3GraphCache,
    StaminaOnlyHC3Problem,
    StaminaOnlySolutionStep,
    analyze_stamina_only_hc3,
)
from utils.map_analysis import shortest_path_length


class EnergyState(Protocol):
    grid: list[list[int]]
    start: tuple[int, int]
    door: tuple[int, int]


class StaminaAwareEnergyState(EnergyState, Protocol):
    items: tuple[object, ...]
    initial_stamina: int
    locked_door: bool


STAMINA_ENERGY_CACHE = StaminaOnlyHC3GraphCache()


@dataclass(frozen=True)
class EnergyBreakdown:
    mode: str
    total_energy: float
    path_target: int | None = None
    path_actual: int | None = None
    path_term: float | None = None
    remaining_stamina_target: float | None = None
    remaining_stamina_actual: float | None = None
    remaining_stamina_term: float | None = None
    remaining_stamina_score: float | None = None
    spacing_target: float | None = None
    spacing_actual: float | None = None
    spacing_score: float | None = None
    spacing_term: float | None = None
    agent_difficulty_target: float | None = None
    agent_difficulty_actual: float | None = None
    agent_difficulty_term: float | None = None
    agent_success_rate: float | None = None
    segment_success_target: float | None = None
    segment_target_score: float | None = None
    segment_target_term: float | None = None
    segment_balance_penalty: float | None = None
    segment_balance_score: float | None = None
    segment_balance_term: float | None = None
    dead_segment_ratio: float | None = None
    dead_segment_term: float | None = None
    stamina_usage_target: float | None = None
    stamina_usage_actual: float | None = None
    stamina_usage_score: float | None = None
    stamina_usage_term: float | None = None
    agent_difficulty_summary: AgentDifficultySummary | None = None
    solution_steps: tuple[StaminaOnlySolutionStep, ...] = ()


def path_length_target_energy(state: EnergyState, target_path_length: int) -> float:
    path_length = shortest_path_length(state.grid, state.start, state.door)

    if path_length is None:
        return math.inf

    return abs(path_length - target_path_length)


def make_path_length_energy(target_path_length: int) -> Callable[[EnergyState], float]:
    def energy_function(state: EnergyState) -> float:
        return path_length_target_energy(state, target_path_length)

    return energy_function


def stamina_aware_baseline_energy(
    state: StaminaAwareEnergyState,
    target_path_length: int,
    target_remaining_stamina: int = 0,
    path_weight: float = 1.0,
    stamina_weight: float = 1.0,
) -> float:
    analysis = analyze_stamina_only_hc3(
        problem=StaminaOnlyHC3Problem(
            grid=state.grid,
            start=state.start,
            door=state.door,
            items=state.items,
            initial_stamina=state.initial_stamina,
            locked_door=state.locked_door,
        ),
        cache=STAMINA_ENERGY_CACHE,
    )

    if (
        not analysis.solvable
        or analysis.shortest_success_path_length is None
        or analysis.best_remaining_stamina is None
    ):
        return math.inf

    path_term = abs(analysis.shortest_success_path_length - target_path_length)
    stamina_term = abs(analysis.best_remaining_stamina - target_remaining_stamina)
    return (path_weight * path_term) + (stamina_weight * stamina_term)


def stamina_aware_baseline_energy_breakdown(
    state: StaminaAwareEnergyState,
    target_path_length: int,
    target_remaining_stamina: int = 0,
    path_weight: float = 1.0,
    stamina_weight: float = 1.0,
) -> EnergyBreakdown:
    analysis = analyze_stamina_only_hc3(
        problem=StaminaOnlyHC3Problem(
            grid=state.grid,
            start=state.start,
            door=state.door,
            items=state.items,
            initial_stamina=state.initial_stamina,
            locked_door=state.locked_door,
        ),
        cache=STAMINA_ENERGY_CACHE,
    )

    if (
        not analysis.solvable
        or analysis.shortest_success_path_length is None
        or analysis.best_remaining_stamina is None
    ):
        return EnergyBreakdown(mode="stamina_only", total_energy=math.inf)

    path_term = path_weight * abs(analysis.shortest_success_path_length - target_path_length)
    stamina_term = stamina_weight * abs(analysis.best_remaining_stamina - target_remaining_stamina)
    return EnergyBreakdown(
        mode="stamina_only",
        total_energy=path_term + stamina_term,
        path_target=target_path_length,
        path_actual=analysis.shortest_success_path_length,
        path_term=path_term,
        remaining_stamina_target=target_remaining_stamina,
        remaining_stamina_actual=analysis.best_remaining_stamina,
        remaining_stamina_term=stamina_term,
        solution_steps=analysis.solution_steps,
    )


def make_stamina_aware_baseline_energy(
    target_path_length: int,
    target_remaining_stamina: int = 0,
    path_weight: float = 1.0,
    stamina_weight: float = 1.0,
) -> Callable[[StaminaAwareEnergyState], float]:
    def energy_function(state: StaminaAwareEnergyState) -> float:
        return stamina_aware_baseline_energy(
            state=state,
            target_path_length=target_path_length,
            target_remaining_stamina=target_remaining_stamina,
            path_weight=path_weight,
            stamina_weight=stamina_weight,
        )

    return energy_function


def stamina_agent_difficulty_energy(
    state: StaminaAwareEnergyState,
    target_agent_difficulty: float = 0.5,
    difficulty_weight: float = 20.0,
    segment_target_weight: float = 10.0,
    segment_balance_weight: float = 10.0,
    dead_segment_weight: float = 10.0,
    stamina_usage_weight: float = 10.0,
    target_stamina_usage_rate: float | None = None,
    final_stamina_weight: float = 10.0,
    final_stamina_target_factor: float = 0.8,
    spacing_weight: float = 10.0,
    spacing_target_scale: float = 1.5,
    agent_config: AgentDifficultyConfig = AgentDifficultyConfig(),
) -> float:
    breakdown = stamina_agent_difficulty_energy_breakdown(
        state=state,
        target_agent_difficulty=target_agent_difficulty,
        difficulty_weight=difficulty_weight,
        segment_target_weight=segment_target_weight,
        segment_balance_weight=segment_balance_weight,
        dead_segment_weight=dead_segment_weight,
        stamina_usage_weight=stamina_usage_weight,
        target_stamina_usage_rate=target_stamina_usage_rate,
        final_stamina_weight=final_stamina_weight,
        final_stamina_target_factor=final_stamina_target_factor,
        spacing_weight=spacing_weight,
        spacing_target_scale=spacing_target_scale,
        agent_config=agent_config,
    )
    return breakdown.total_energy


def stamina_agent_difficulty_energy_breakdown(
    state: StaminaAwareEnergyState,
    target_agent_difficulty: float = 0.5,
    difficulty_weight: float = 20.0,
    segment_target_weight: float = 10.0,
    segment_balance_weight: float = 10.0,
    dead_segment_weight: float = 10.0,
    stamina_usage_weight: float = 10.0,
    target_stamina_usage_rate: float | None = None,
    final_stamina_weight: float = 10.0,
    final_stamina_target_factor: float = 0.8,
    spacing_weight: float = 10.0,
    spacing_target_scale: float = 1.5,
    agent_config: AgentDifficultyConfig = AgentDifficultyConfig(),
) -> EnergyBreakdown:
    difficulty_summary = estimate_agent_difficulty(
        problem=StaminaOnlyHC3Problem(
            grid=state.grid,
            start=state.start,
            door=state.door,
            items=state.items,
            initial_stamina=state.initial_stamina,
            locked_door=state.locked_door,
        ),
        config=agent_config,
        cache=STAMINA_ENERGY_CACHE,
    )
    difficulty_term = difficulty_weight * abs(
        difficulty_summary.main_route_difficulty - target_agent_difficulty
    )
    segment_success_target, segment_target_score = _segment_target_alignment(
        difficulty_summary=difficulty_summary,
        target_agent_difficulty=target_agent_difficulty,
    )
    segment_target_term = segment_target_weight * segment_target_score
    segment_balance_score = min(1.0, 2.0 * difficulty_summary.segment_success_std)
    segment_balance_term = segment_balance_weight * segment_balance_score
    dead_segment_term = dead_segment_weight * difficulty_summary.dead_segment_ratio
    stamina_usage_target = _target_stamina_usage_rate(
        state=state,
        target_agent_difficulty=target_agent_difficulty,
        target_stamina_usage_rate=target_stamina_usage_rate,
    )
    stamina_usage_actual = _weighted_stamina_plan_usage_rate(
        state=state,
        difficulty_summary=difficulty_summary,
    )
    stamina_usage_score = abs(stamina_usage_target - stamina_usage_actual)
    stamina_usage_term = stamina_usage_weight * stamina_usage_score
    final_stamina_difficulty_scale = 1.0 - target_agent_difficulty
    final_stamina_target = (
        final_stamina_target_factor
        * state.initial_stamina
        * final_stamina_difficulty_scale
    )
    weighted_final_stamina = _weighted_agent_final_stamina(difficulty_summary)
    stamina_normalizer = max(1.0, float(state.initial_stamina))
    final_stamina_score = min(
        1.0,
        abs(final_stamina_target - weighted_final_stamina) / stamina_normalizer,
    )
    final_stamina_term = final_stamina_weight * final_stamina_score
    spacing_actual = _start_key_door_path_spacing(state)
    spacing_target = _target_path_spacing(
        state=state,
        target_agent_difficulty=target_agent_difficulty,
        spacing_target_scale=spacing_target_scale,
    )
    spacing_normalizer = max(1.0, spacing_target)
    spacing_error_ratio = abs(spacing_target - spacing_actual) / spacing_normalizer
    spacing_score = min(1.0, spacing_error_ratio * spacing_error_ratio)
    spacing_term = spacing_weight * spacing_score

    return EnergyBreakdown(
        mode="stamina_agent_difficulty",
        total_energy=(
            difficulty_term
            + segment_target_term
            + segment_balance_term
            + dead_segment_term
            + stamina_usage_term
            + final_stamina_term
            + spacing_term
        ),
        agent_difficulty_target=target_agent_difficulty,
        agent_difficulty_actual=difficulty_summary.main_route_difficulty,
        agent_difficulty_term=difficulty_term,
        agent_success_rate=difficulty_summary.main_route_success_rate,
        segment_success_target=segment_success_target,
        segment_target_score=segment_target_score,
        segment_target_term=segment_target_term,
        remaining_stamina_target=final_stamina_target,
        remaining_stamina_actual=weighted_final_stamina,
        remaining_stamina_score=final_stamina_score,
        remaining_stamina_term=final_stamina_term,
        spacing_target=spacing_target,
        spacing_actual=spacing_actual,
        spacing_score=spacing_score,
        spacing_term=spacing_term,
        segment_balance_penalty=difficulty_summary.segment_success_std,
        segment_balance_score=segment_balance_score,
        segment_balance_term=segment_balance_term,
        dead_segment_ratio=difficulty_summary.dead_segment_ratio,
        dead_segment_term=dead_segment_term,
        stamina_usage_target=stamina_usage_target,
        stamina_usage_actual=stamina_usage_actual,
        stamina_usage_score=stamina_usage_score,
        stamina_usage_term=stamina_usage_term,
        agent_difficulty_summary=difficulty_summary,
    )


def make_stamina_agent_difficulty_energy(
    target_agent_difficulty: float = 0.5,
    difficulty_weight: float = 20.0,
    segment_target_weight: float = 10.0,
    segment_balance_weight: float = 10.0,
    dead_segment_weight: float = 10.0,
    stamina_usage_weight: float = 10.0,
    target_stamina_usage_rate: float | None = None,
    final_stamina_weight: float = 10.0,
    final_stamina_target_factor: float = 0.8,
    spacing_weight: float = 10.0,
    spacing_target_scale: float = 1.5,
    agent_config: AgentDifficultyConfig = AgentDifficultyConfig(),
) -> Callable[[StaminaAwareEnergyState], float]:
    def energy_function(state: StaminaAwareEnergyState) -> float:
        return stamina_agent_difficulty_energy(
            state=state,
            target_agent_difficulty=target_agent_difficulty,
            difficulty_weight=difficulty_weight,
            segment_target_weight=segment_target_weight,
            segment_balance_weight=segment_balance_weight,
            dead_segment_weight=dead_segment_weight,
            stamina_usage_weight=stamina_usage_weight,
            target_stamina_usage_rate=target_stamina_usage_rate,
            final_stamina_weight=final_stamina_weight,
            final_stamina_target_factor=final_stamina_target_factor,
            spacing_weight=spacing_weight,
            spacing_target_scale=spacing_target_scale,
            agent_config=agent_config,
        )

    return energy_function


def _weighted_agent_final_stamina(difficulty_summary: AgentDifficultySummary) -> float:
    weighted_stamina_sum = 0.0
    success_rate_sum = 0.0

    for plan_summary in difficulty_summary.plan_summaries:
        if not plan_summary.plan.semantic_success:
            continue

        if plan_summary.estimated_success_rate <= 0.0:
            continue

        if not plan_summary.final_stamina_samples:
            continue

        average_final_stamina = sum(plan_summary.final_stamina_samples) / len(
            plan_summary.final_stamina_samples
        )
        weighted_stamina_sum += plan_summary.estimated_success_rate * average_final_stamina
        success_rate_sum += plan_summary.estimated_success_rate

    if success_rate_sum <= 0.0:
        return 0.0

    return weighted_stamina_sum / success_rate_sum


def _segment_target_alignment(
    *,
    difficulty_summary: AgentDifficultySummary,
    target_agent_difficulty: float,
) -> tuple[float, float]:
    target_route_success_rate = _clamp01(1.0 - target_agent_difficulty)
    segment_targets: list[float] = []
    segment_deviations: list[float] = []

    for plan_summary in difficulty_summary.plan_summaries:
        if not plan_summary.plan.semantic_success:
            continue

        segment_count = len(plan_summary.segment_summaries)

        if segment_count == 0:
            continue

        segment_success_target = target_route_success_rate ** (1.0 / segment_count)

        for segment in plan_summary.segment_summaries:
            segment_targets.append(segment_success_target)
            segment_deviations.append(abs(segment.success_rate - segment_success_target))

    if not segment_deviations:
        return 0.0, 0.0

    return _average(segment_targets), min(1.0, _average(segment_deviations))


def _weighted_stamina_plan_usage_rate(
    *,
    state: StaminaAwareEnergyState,
    difficulty_summary: AgentDifficultySummary,
) -> float:
    total_stamina_item_count = sum(
        1
        for item in state.items
        if getattr(item, "kind", None) == "stamina"
    )

    if total_stamina_item_count == 0:
        return 0.0

    weighted_usage_sum = 0.0
    success_rate_sum = 0.0

    for plan_summary in difficulty_summary.plan_summaries:
        if not plan_summary.plan.semantic_success:
            continue

        if plan_summary.estimated_success_rate <= 0.0:
            continue

        collected_stamina_count = sum(
            1
            for step in plan_summary.plan.steps
            if step.kind == "item:stamina"
        )
        stamina_collection_ratio = min(
            1.0,
            collected_stamina_count / total_stamina_item_count,
        )
        weighted_usage_sum += plan_summary.estimated_success_rate * stamina_collection_ratio
        success_rate_sum += plan_summary.estimated_success_rate

    if success_rate_sum <= 0.0:
        return 0.0

    return weighted_usage_sum / success_rate_sum


def _target_stamina_usage_rate(
    *,
    state: StaminaAwareEnergyState,
    target_agent_difficulty: float,
    target_stamina_usage_rate: float | None,
) -> float:
    has_stamina_item = any(
        getattr(item, "kind", None) == "stamina"
        for item in state.items
    )

    if not has_stamina_item:
        return 0.0

    if target_stamina_usage_rate is not None:
        return _clamp01(target_stamina_usage_rate)

    return _clamp01(target_agent_difficulty)


def _start_key_door_path_spacing(state: StaminaAwareEnergyState) -> float:
    key_item = next(
        (item for item in state.items if getattr(item, "kind", None) == "key"),
        None,
    )

    if key_item is None:
        return float(_shortest_path_distance_or_zero(state.grid, state.start, state.door))

    distances = (
        _shortest_path_distance_or_zero(state.grid, state.start, key_item.position),
        _shortest_path_distance_or_zero(state.grid, key_item.position, state.door),
    )
    return sum(distances) / len(distances)


def _shortest_path_distance_or_zero(
    grid: list[list[int]],
    first_position: tuple[int, int],
    second_position: tuple[int, int],
) -> float:
    distance = shortest_path_length(grid, first_position, second_position)

    if distance is None:
        return 0.0

    return float(distance)


def _target_path_spacing(
    state: StaminaAwareEnergyState,
    target_agent_difficulty: float,
    spacing_target_scale: float,
) -> float:
    grid_scale = _grid_path_scale(state.grid)
    difficulty_scale = 0.5 + (0.5 * target_agent_difficulty)
    return spacing_target_scale * grid_scale * difficulty_scale


def _grid_path_scale(grid: list[list[int]]) -> float:
    height = len(grid)
    width = len(grid[0]) if height else 0
    return math.sqrt(max(1, height * width))


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def path_length_energy_breakdown(
    state: EnergyState,
    target_path_length: int,
) -> EnergyBreakdown:
    path_length = shortest_path_length(state.grid, state.start, state.door)

    if path_length is None:
        return EnergyBreakdown(mode="door_only", total_energy=math.inf)

    path_term = abs(path_length - target_path_length)
    return EnergyBreakdown(
        mode="door_only",
        total_energy=path_term,
        path_target=target_path_length,
        path_actual=path_length,
        path_term=path_term,
    )
