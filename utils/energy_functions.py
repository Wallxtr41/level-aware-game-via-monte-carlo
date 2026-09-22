from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Protocol

from utils.agent_difficulty import (
    AgentDifficultyConfig,
    AgentDifficultySummary,
    PlanSimulationSummary,
    estimate_agent_difficulty,
)
from utils.hard_constraints import (
    StaminaOnlyHC3GraphCache,
    StaminaOnlyHC3Problem,
    StaminaOnlySolutionStep,
    analyze_stamina_only_hc3,
)
from utils.map_analysis import (
    is_walkable,
    iter_neighbors,
    shortest_path_length,
    shortest_path_length_with_blocked,
)


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
    effective_success_rate: float | None = None
    coverage_target: float | None = None
    coverage_actual: float | None = None
    coverage_score: float | None = None
    coverage_term: float | None = None
    branching_target: float | None = None
    branching_actual: float | None = None
    branching_score: float | None = None
    branching_term: float | None = None
    junction_density: float | None = None
    trap_depth_score: float | None = None
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
    coverage_weight: float = 10.0,
    coverage_target_base: float = 0.15,
    coverage_target_difficulty_scale: float = 0.55,
    branching_weight: float = 10.0,
    branching_target_base: float = 0.2,
    branching_target_difficulty_scale: float = 0.5,
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
        coverage_weight=coverage_weight,
        coverage_target_base=coverage_target_base,
        coverage_target_difficulty_scale=coverage_target_difficulty_scale,
        branching_weight=branching_weight,
        branching_target_base=branching_target_base,
        branching_target_difficulty_scale=branching_target_difficulty_scale,
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
    coverage_weight: float = 10.0,
    coverage_target_base: float = 0.15,
    coverage_target_difficulty_scale: float = 0.55,
    branching_weight: float = 10.0,
    branching_target_base: float = 0.2,
    branching_target_difficulty_scale: float = 0.5,
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
    # Oyuncu en kolay rotayi oynar: plan basari oranlarinin basari-agirlikli
    # ortalamasi (average <= R_eff <= max) ana zorluk sinyalidir.
    effective_success_rate = _effective_route_success_rate(difficulty_summary)
    effective_difficulty = 1.0 - effective_success_rate
    difficulty_term = difficulty_weight * abs(
        effective_difficulty - target_agent_difficulty
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
    # Min-bazli usage: oyuncunun yirtabilecegi en dusuk item kullanimi. 0 ise
    # harita item'siz bitirilebilir demektir; hedefe uzaklik cezalandirilir.
    stamina_usage_actual = _min_viable_stamina_usage(
        state=state,
        difficulty_summary=difficulty_summary,
    )
    stamina_usage_score = abs(stamina_usage_target - stamina_usage_actual)
    stamina_usage_term = stamina_usage_weight * stamina_usage_score
    best_plan_summary = _best_solvable_plan_summary(difficulty_summary)
    coverage_actual = _agent_coverage(
        state=state,
        best_plan_summary=best_plan_summary,
    )
    coverage_target = _clamp01(
        coverage_target_base
        + coverage_target_difficulty_scale * target_agent_difficulty
    )
    coverage_score = min(1.0, abs(coverage_target - coverage_actual))
    coverage_term = coverage_weight * coverage_score
    junction_density, trap_depth_score = _solution_branching(
        state=state,
        best_plan_summary=best_plan_summary,
    )
    # HC2'li maze'lerde junction_density dogal olarak ~[0, 0.35] araliginda
    # kalir; tam [0, 1] skalasina normalize edilir.
    junction_score = min(1.0, junction_density / 0.35)
    branching_actual = (0.5 * junction_score) + (0.5 * trap_depth_score)
    branching_target = _clamp01(
        branching_target_base
        + branching_target_difficulty_scale * target_agent_difficulty
    )
    # Tek tarafli ceza: HC1 yan koridorlarin kapatilmasina izin vermedigi icin
    # dallanmayi dusurmek cogu zaman imkansizdir; sadece hedefin altinda kalan
    # (fazla obvious) yollar cezalandirilir.
    branching_score = min(1.0, max(0.0, branching_target - branching_actual))
    branching_term = branching_weight * branching_score
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
            + coverage_term
            + branching_term
        ),
        agent_difficulty_target=target_agent_difficulty,
        agent_difficulty_actual=effective_difficulty,
        agent_difficulty_term=difficulty_term,
        agent_success_rate=effective_success_rate,
        effective_success_rate=effective_success_rate,
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
        coverage_target=coverage_target,
        coverage_actual=coverage_actual,
        coverage_score=coverage_score,
        coverage_term=coverage_term,
        branching_target=branching_target,
        branching_actual=branching_actual,
        branching_score=branching_score,
        branching_term=branching_term,
        junction_density=junction_density,
        trap_depth_score=trap_depth_score,
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
    coverage_weight: float = 10.0,
    coverage_target_base: float = 0.15,
    coverage_target_difficulty_scale: float = 0.55,
    branching_weight: float = 10.0,
    branching_target_base: float = 0.2,
    branching_target_difficulty_scale: float = 0.5,
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
            coverage_weight=coverage_weight,
            coverage_target_base=coverage_target_base,
            coverage_target_difficulty_scale=coverage_target_difficulty_scale,
            branching_weight=branching_weight,
            branching_target_base=branching_target_base,
            branching_target_difficulty_scale=branching_target_difficulty_scale,
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


def _effective_route_success_rate(difficulty_summary: AgentDifficultySummary) -> float:
    solvable_success_rates = [
        plan_summary.estimated_success_rate
        for plan_summary in difficulty_summary.plan_summaries
        if plan_summary.plan.semantic_success
    ]
    success_rate_sum = sum(solvable_success_rates)

    if success_rate_sum <= 0.0:
        return 0.0

    return sum(rate * rate for rate in solvable_success_rates) / success_rate_sum


def _min_viable_stamina_usage(
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

    min_usage: float | None = None

    for plan_summary in difficulty_summary.plan_summaries:
        if not plan_summary.plan.semantic_success:
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

        if min_usage is None or stamina_collection_ratio < min_usage:
            min_usage = stamina_collection_ratio

    return min_usage if min_usage is not None else 0.0


def _best_solvable_plan_summary(
    difficulty_summary: AgentDifficultySummary,
) -> PlanSimulationSummary | None:
    solvable_plan_summaries = [
        plan_summary
        for plan_summary in difficulty_summary.plan_summaries
        if plan_summary.plan.semantic_success
    ]

    if not solvable_plan_summaries:
        return None

    return max(
        solvable_plan_summaries,
        key=lambda plan_summary: plan_summary.estimated_success_rate,
    )


def _agent_coverage(
    *,
    state: StaminaAwareEnergyState,
    best_plan_summary: PlanSimulationSummary | None,
) -> float:
    if best_plan_summary is None:
        return 0.0

    walkable_count = _walkable_cell_count(state.grid)

    if walkable_count == 0:
        return 0.0

    expected_visited = sum(
        segment.average_success_visited_count
        for segment in best_plan_summary.segment_summaries
    )
    return min(1.0, expected_visited / walkable_count)


def _solution_branching(
    *,
    state: StaminaAwareEnergyState,
    best_plan_summary: PlanSimulationSummary | None,
) -> tuple[float, float]:
    if best_plan_summary is None:
        return 0.0, 0.0

    path_cells = _expand_best_plan_path(state, best_plan_summary)

    if len(path_cells) < 2:
        return 0.0, 0.0

    junction_cell_count = 0
    branch_entrances: set[tuple[int, int]] = set()

    for position in path_cells:
        off_path_neighbors = [
            neighbor
            for neighbor in iter_neighbors(*position)
            if neighbor not in path_cells
            and is_walkable(state.grid, neighbor[0], neighbor[1])
        ]

        if off_path_neighbors:
            junction_cell_count += 1
            branch_entrances.update(off_path_neighbors)

    junction_density = min(1.0, junction_cell_count / len(path_cells))
    grid_scale = _grid_path_scale(state.grid)
    deep_trap_threshold = max(2.0, 0.25 * grid_scale)
    trap_depths = [
        _branch_depth(state.grid, entrance, path_cells)
        for entrance in branch_entrances
    ]
    # Ortalama dal derinligi maze'lerde hep sature oldugu icin sinyal olarak
    # "derin tuzak orani" kullanilir: esik uzeri dallarin tum dallara orani.
    trap_depth_score = (
        sum(1 for depth in trap_depths if depth >= deep_trap_threshold) / len(trap_depths)
        if trap_depths
        else 0.0
    )
    return junction_density, trap_depth_score


def _branch_depth(
    grid: list[list[int]],
    entrance: tuple[int, int],
    path_cells: set[tuple[int, int]],
) -> float:
    frontier = [entrance]
    depth_by_position = {entrance: 1}
    max_depth = 1

    while frontier:
        position = frontier.pop()
        depth = depth_by_position[position]
        max_depth = max(max_depth, depth)

        for neighbor in iter_neighbors(*position):
            if neighbor in path_cells or neighbor in depth_by_position:
                continue

            if not is_walkable(grid, neighbor[0], neighbor[1]):
                continue

            depth_by_position[neighbor] = depth + 1
            frontier.append(neighbor)

    return float(max_depth)


def _expand_best_plan_path(
    state: StaminaAwareEnergyState,
    best_plan_summary: PlanSimulationSummary,
) -> set[tuple[int, int]]:
    steps = best_plan_summary.plan.steps
    item_index_by_position = {
        item.position: item_index for item_index, item in enumerate(state.items)
    }
    collected_positions = {steps[0].position}
    path_cells: set[tuple[int, int]] = {steps[0].position}

    for source_step, target_step in zip(steps, steps[1:]):
        blocked_positions = {
            item.position
            for item in state.items
            if item.position not in collected_positions
            and item.position not in {source_step.position, target_step.position}
        }

        if state.door not in {source_step.position, target_step.position}:
            blocked_positions.add(state.door)

        leg_path = _bfs_path(
            state.grid,
            source_step.position,
            target_step.position,
            blocked_positions=blocked_positions,
        )

        if leg_path is not None:
            path_cells.update(leg_path)

        if target_step.position in item_index_by_position:
            collected_positions.add(target_step.position)

    return path_cells


def _bfs_path(
    grid: list[list[int]],
    source: tuple[int, int],
    target: tuple[int, int],
    *,
    blocked_positions: set[tuple[int, int]],
) -> list[tuple[int, int]] | None:
    if source == target:
        return [source]

    queue = [source]
    parents: dict[tuple[int, int], tuple[int, int] | None] = {source: None}

    while queue:
        position = queue.pop(0)

        for neighbor in iter_neighbors(*position):
            if neighbor in parents or neighbor in blocked_positions:
                continue

            if not is_walkable(grid, neighbor[0], neighbor[1]):
                continue

            parents[neighbor] = position

            if neighbor == target:
                path = [target]
                cursor: tuple[int, int] | None = position

                while cursor is not None:
                    path.append(cursor)
                    cursor = parents[cursor]

                path.reverse()
                return path

            queue.append(neighbor)

    return None


def _walkable_cell_count(grid: list[list[int]]) -> int:
    return sum(1 for row in grid for cell in row if cell == 0)


def _target_stamina_usage_rate(
    *,
    state: StaminaAwareEnergyState,
    target_agent_difficulty: float,
    target_stamina_usage_rate: float | None,
) -> float:
    stamina_item_count = sum(
        1
        for item in state.items
        if getattr(item, "kind", None) == "stamina"
    )

    if stamina_item_count == 0:
        return 0.0

    if target_stamina_usage_rate is not None:
        raw_target = _clamp01(target_stamina_usage_rate)
    else:
        raw_target = _clamp01(target_agent_difficulty)

    # min_usage sadece k/n degerlerini alabilir; hedef ulasilamaz bir ara
    # degerde kalirsa terim sabit bir ceza tabanina yapisir.
    return round(raw_target * stamina_item_count) / stamina_item_count


def _start_key_door_path_spacing(state: StaminaAwareEnergyState) -> float:
    key_item = next(
        (item for item in state.items if getattr(item, "kind", None) == "key"),
        None,
    )

    if key_item is None:
        return float(
            _shortest_path_distance_or_zero(
                state.grid,
                state.start,
                state.door,
            )
        )

    distances = (
        _shortest_path_distance_or_zero(
            state.grid,
            state.start,
            key_item.position,
            blocked_positions={state.door} if state.locked_door else set(),
        ),
        _shortest_path_distance_or_zero(
            state.grid,
            key_item.position,
            state.door,
        ),
    )
    return sum(distances) / len(distances)


def _shortest_path_distance_or_zero(
    grid: list[list[int]],
    first_position: tuple[int, int],
    second_position: tuple[int, int],
    blocked_positions: set[tuple[int, int]] | None = None,
) -> float:
    if blocked_positions:
        distance = shortest_path_length_with_blocked(
            grid,
            first_position,
            second_position,
            blocked_positions=blocked_positions,
        )
    else:
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
