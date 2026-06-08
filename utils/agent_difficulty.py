from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import random
from typing import Iterable

from utils.hard_constraints import StaminaOnlyHC3GraphCache
from utils.hard_constraints.hc3_stamina_only_solver import (
    StaminaNode,
    StaminaOnlyGraph,
    StaminaOnlyHC3Problem,
    StaminaOnlyState,
    build_stamina_only_hc3_graph,
)
from utils.map_analysis import is_walkable, iter_neighbors
from utils.map_entities import Position


@dataclass(frozen=True)
class SemanticPlanStep:
    node_id: int
    position: Position
    kind: str
    edge_cost: int
    remaining_stamina: int


@dataclass(frozen=True)
class SemanticSolutionPlan:
    steps: tuple[SemanticPlanStep, ...]
    semantic_success: bool
    shortest_cost: int | None = None
    final_stamina: int | None = None

    @property
    def node_ids(self) -> tuple[int, ...]:
        return tuple(step.node_id for step in self.steps)


@dataclass(frozen=True)
class SegmentAgentResult:
    success: bool
    start_stamina: int
    remaining_stamina: int
    total_steps: int
    revisits: int
    forced_backtracks: int


@dataclass(frozen=True)
class SegmentSimulationSummary:
    source_node_id: int
    target_node_id: int
    source_position: Position
    target_position: Position
    agent_results: tuple[SegmentAgentResult, ...]
    output_stamina_samples: tuple[int, ...]

    @property
    def agent_count(self) -> int:
        return len(self.agent_results)

    @property
    def success_count(self) -> int:
        return len(self.output_stamina_samples)

    @property
    def success_rate(self) -> float:
        if not self.agent_results:
            return 0.0
        return self.success_count / len(self.agent_results)

    @property
    def average_steps(self) -> float:
        return _average(result.total_steps for result in self.agent_results)

    @property
    def average_revisits(self) -> float:
        return _average(result.revisits for result in self.agent_results)

    @property
    def average_forced_backtracks(self) -> float:
        return _average(result.forced_backtracks for result in self.agent_results)

    @property
    def average_success_remaining_stamina(self) -> float:
        return _average(self.output_stamina_samples)


@dataclass(frozen=True)
class PlanSimulationSummary:
    plan: SemanticSolutionPlan
    segment_summaries: tuple[SegmentSimulationSummary, ...]
    estimated_success_rate: float
    final_stamina_samples: tuple[int, ...]


@dataclass(frozen=True)
class AgentDifficultyConfig:
    agents_per_segment: int = 30
    random_seed: int = 12345


@dataclass(frozen=True)
class AgentDifficultySummary:
    solvable: bool
    semantic_plan_count: int
    simulated_plan_count: int
    average_plan_success_rate: float
    best_plan_success_rate: float
    difficulty_score: float
    main_route_success_rate: float
    main_route_difficulty: float
    segment_success_std: float
    dead_segment_count: int
    unique_segment_count: int
    dead_segment_ratio: float
    plan_summaries: tuple[PlanSimulationSummary, ...]


_DIFFICULTY_CACHE: dict[tuple[object, ...], AgentDifficultySummary] = {}


def estimate_agent_difficulty(
    problem: StaminaOnlyHC3Problem,
    config: AgentDifficultyConfig = AgentDifficultyConfig(),
    cache: StaminaOnlyHC3GraphCache | None = None,
) -> AgentDifficultySummary:
    cache_key = _difficulty_cache_key(problem, config)
    cached_summary = _DIFFICULTY_CACHE.get(cache_key)

    if cached_summary is not None:
        return cached_summary

    graph, _ = build_stamina_only_hc3_graph(problem, cache=cache)
    plans = enumerate_semantic_solution_plans(
        problem=problem,
        graph=graph,
    )

    if not plans:
        summary = AgentDifficultySummary(
            solvable=False,
            semantic_plan_count=0,
            simulated_plan_count=0,
            average_plan_success_rate=0.0,
            best_plan_success_rate=0.0,
            difficulty_score=1.0,
            main_route_success_rate=0.0,
            main_route_difficulty=1.0,
            segment_success_std=0.0,
            dead_segment_count=0,
            unique_segment_count=0,
            dead_segment_ratio=0.0,
            plan_summaries=(),
        )
        _DIFFICULTY_CACHE[cache_key] = summary
        return summary

    plan_summaries = tuple(
        simulate_semantic_plan(
            problem=problem,
            graph=graph,
            plan=plan,
            config=config,
        )
        for plan in plans
    )
    best_success_rate = max(
        (plan_summary.estimated_success_rate for plan_summary in plan_summaries),
        default=0.0,
    )
    solvable_success_rates = tuple(
        plan_summary.estimated_success_rate
        for plan_summary in plan_summaries
        if plan_summary.plan.semantic_success
    )
    main_route_success_rate = _average(solvable_success_rates)
    main_route_difficulty = 1.0 - main_route_success_rate
    attempted_segment_rates_by_key = _get_attempted_segment_rates_by_key(plan_summaries)
    unique_attempted_segment_rates = tuple(
        _average(segment_rates)
        for segment_rates in attempted_segment_rates_by_key.values()
    )
    segment_success_std = _standard_deviation(unique_attempted_segment_rates)
    exact_dead_segment_keys = _get_exact_dead_segment_keys(plans)
    unique_segment_keys = set(attempted_segment_rates_by_key) | exact_dead_segment_keys
    dead_segment_keys = exact_dead_segment_keys
    dead_segment_ratio = (
        len(dead_segment_keys) / len(unique_segment_keys)
        if unique_segment_keys
        else 0.0
    )
    summary = AgentDifficultySummary(
        solvable=any(plan.semantic_success for plan in plans),
        semantic_plan_count=len(plans),
        simulated_plan_count=sum(1 for plan in plans if plan.semantic_success),
        average_plan_success_rate=main_route_success_rate,
        best_plan_success_rate=best_success_rate,
        difficulty_score=main_route_difficulty,
        main_route_success_rate=main_route_success_rate,
        main_route_difficulty=main_route_difficulty,
        segment_success_std=segment_success_std,
        dead_segment_count=len(dead_segment_keys),
        unique_segment_count=len(unique_segment_keys),
        dead_segment_ratio=dead_segment_ratio,
        plan_summaries=plan_summaries,
    )
    _DIFFICULTY_CACHE[cache_key] = summary
    return summary


def enumerate_semantic_solution_plans(
    problem: StaminaOnlyHC3Problem,
    graph: StaminaOnlyGraph | None = None,
) -> tuple[SemanticSolutionPlan, ...]:
    graph = graph or build_stamina_only_hc3_graph(problem)[0]
    start_state = _collect_node_effects(
        problem,
        graph,
        StaminaOnlyState(
            node_id=graph.position_to_node[problem.start],
            remaining_stamina=problem.initial_stamina,
            collected_items_mask=0,
            has_key=False,
        ),
    )
    start_node = graph.nodes[start_state.node_id]
    start_step = _make_plan_step(start_node, edge_cost=0, remaining_stamina=start_state.remaining_stamina)
    plans: list[SemanticSolutionPlan] = []

    def dfs(
        current_node_id: int,
        steps: tuple[SemanticPlanStep, ...],
        visited_node_ids: frozenset[int],
    ) -> None:
        for target_node_id, edge_cost in _get_candidate_semantic_edges(graph, current_node_id):
            target_node = graph.nodes[target_node_id]

            if target_node.kind != "door" and target_node_id in visited_node_ids:
                continue

            next_step = _make_plan_step(
                target_node,
                edge_cost=edge_cost,
                remaining_stamina=0,
            )
            next_steps = (*steps, next_step)

            if target_node.kind == "door":
                plans.append(_score_semantic_plan(problem, graph, next_steps))
                continue

            dfs(
                target_node_id,
                next_steps,
                frozenset((*visited_node_ids, target_node_id)),
            )

    dfs(start_state.node_id, (start_step,), frozenset({start_state.node_id}))
    return tuple(plans)


def simulate_semantic_plan(
    problem: StaminaOnlyHC3Problem,
    graph: StaminaOnlyGraph,
    plan: SemanticSolutionPlan,
    config: AgentDifficultyConfig,
) -> PlanSimulationSummary:
    if not plan.semantic_success:
        return PlanSimulationSummary(
            plan=plan,
            segment_summaries=(),
            estimated_success_rate=0.0,
            final_stamina_samples=(),
        )

    incoming_stamina_samples = (problem.initial_stamina,)
    segment_summaries: list[SegmentSimulationSummary] = []
    estimated_success_rate = 1.0
    collected_items_mask = 0

    for segment_index, (source_step, target_step) in enumerate(zip(plan.steps, plan.steps[1:])):
        source_node = graph.nodes[source_step.node_id]
        target_node = graph.nodes[target_step.node_id]
        door_is_active = _has_key(problem, collected_items_mask) or not problem.locked_door
        segment_seed = _stable_seed(
            (
                "segment",
                config.random_seed,
                plan.node_ids,
                segment_index,
                source_node.position,
                target_node.position,
            )
        )
        segment_summary = simulate_segment_population(
            problem=problem,
            source_node=source_node,
            target_node=target_node,
            incoming_stamina_samples=incoming_stamina_samples,
            collected_items_mask=collected_items_mask,
            door_is_active=door_is_active,
            agent_count=config.agents_per_segment,
            seed=segment_seed,
        )
        segment_summaries.append(segment_summary)
        estimated_success_rate *= segment_summary.success_rate

        if target_node.item_index is not None:
            collected_items_mask |= 1 << target_node.item_index

        incoming_stamina_samples = segment_summary.output_stamina_samples

        if not incoming_stamina_samples:
            break

    return PlanSimulationSummary(
        plan=plan,
        segment_summaries=tuple(segment_summaries),
        estimated_success_rate=estimated_success_rate,
        final_stamina_samples=incoming_stamina_samples,
    )


def simulate_segment_population(
    problem: StaminaOnlyHC3Problem,
    source_node: StaminaNode,
    target_node: StaminaNode,
    incoming_stamina_samples: tuple[int, ...],
    collected_items_mask: int,
    door_is_active: bool,
    agent_count: int,
    seed: int,
) -> SegmentSimulationSummary:
    rng = random.Random(seed)
    blocked_positions = {
        item.position
        for item_index, item in enumerate(problem.items)
        if item.position not in {source_node.position, target_node.position}
    }
    blocked_positions.discard(source_node.position)
    blocked_positions.discard(target_node.position)

    if door_is_active and problem.door not in {source_node.position, target_node.position}:
        blocked_positions.add(problem.door)

    agent_results: list[SegmentAgentResult] = []
    output_stamina_samples: list[int] = []

    if not incoming_stamina_samples:
        return SegmentSimulationSummary(
            source_node_id=source_node.node_id,
            target_node_id=target_node.node_id,
            source_position=source_node.position,
            target_position=target_node.position,
            agent_results=(),
            output_stamina_samples=(),
        )

    for _ in range(agent_count):
        start_stamina = rng.choice(incoming_stamina_samples)
        result = simulate_segment_agent(
            grid=problem.grid,
            source=source_node.position,
            target=target_node.position,
            blocked_positions=blocked_positions,
            start_stamina=start_stamina,
            rng=rng,
        )

        if result.success:
            output_stamina_samples.append(
                _apply_target_stamina_effect(
                    problem=problem,
                    target_node=target_node,
                    collected_items_mask=collected_items_mask,
                    remaining_stamina=result.remaining_stamina,
                )
            )

        agent_results.append(result)

    return SegmentSimulationSummary(
        source_node_id=source_node.node_id,
        target_node_id=target_node.node_id,
        source_position=source_node.position,
        target_position=target_node.position,
        agent_results=tuple(agent_results),
        output_stamina_samples=tuple(output_stamina_samples),
    )


def simulate_segment_agent(
    *,
    grid: list[list[int]],
    source: Position,
    target: Position,
    blocked_positions: set[Position],
    start_stamina: int,
    rng: random.Random,
) -> SegmentAgentResult:
    current_position = source
    previous_position: Position | None = None
    visited_positions = {source}
    remaining_stamina = start_stamina
    total_steps = 0
    revisits = 0
    forced_backtracks = 0

    while current_position != target:
        if remaining_stamina <= 0:
            break

        next_position, forced_backtrack = _choose_next_position(
            grid=grid,
            current_position=current_position,
            previous_position=previous_position,
            target=target,
            blocked_positions=blocked_positions,
            visited_positions=visited_positions,
            rng=rng,
        )

        if next_position is None:
            break

        if next_position in visited_positions:
            revisits += 1

        if forced_backtrack:
            forced_backtracks += 1

        previous_position = current_position
        current_position = next_position
        visited_positions.add(current_position)
        remaining_stamina -= 1
        total_steps += 1

    return SegmentAgentResult(
        success=current_position == target and remaining_stamina >= 0,
        start_stamina=start_stamina,
        remaining_stamina=remaining_stamina,
        total_steps=total_steps,
        revisits=revisits,
        forced_backtracks=forced_backtracks,
    )


def _choose_next_position(
    *,
    grid: list[list[int]],
    current_position: Position,
    previous_position: Position | None,
    target: Position,
    blocked_positions: set[Position],
    visited_positions: set[Position],
    rng: random.Random,
) -> tuple[Position | None, bool]:
    valid_neighbors = [
        next_position
        for next_position in iter_neighbors(*current_position)
        if next_position == target
        or (
            next_position not in blocked_positions
            and is_walkable(grid, next_position[0], next_position[1])
        )
    ]

    if not valid_neighbors:
        return None, False

    if target in valid_neighbors:
        return target, False

    unvisited_neighbors = [
        next_position for next_position in valid_neighbors if next_position not in visited_positions
    ]

    if unvisited_neighbors:
        return rng.choice(unvisited_neighbors), False

    non_backtracking_neighbors = [
        next_position for next_position in valid_neighbors if next_position != previous_position
    ]

    if non_backtracking_neighbors:
        return rng.choice(non_backtracking_neighbors), False

    return rng.choice(valid_neighbors), True


def _get_candidate_semantic_edges(
    graph: StaminaOnlyGraph,
    node_id: int,
) -> tuple[tuple[int, int], ...]:
    edge_cost_by_target: dict[int, int] = {}

    for adjacency in (graph.closed_door_adjacency, graph.open_door_adjacency):
        for target_node_id, edge_cost in adjacency[node_id]:
            existing_cost = edge_cost_by_target.get(target_node_id)

            if existing_cost is None or edge_cost < existing_cost:
                edge_cost_by_target[target_node_id] = edge_cost

    return tuple(sorted(edge_cost_by_target.items()))


def _score_semantic_plan(
    problem: StaminaOnlyHC3Problem,
    graph: StaminaOnlyGraph,
    steps: tuple[SemanticPlanStep, ...],
) -> SemanticSolutionPlan:
    state = _collect_node_effects(
        problem,
        graph,
        StaminaOnlyState(
            node_id=steps[0].node_id,
            remaining_stamina=problem.initial_stamina,
            collected_items_mask=0,
            has_key=False,
        ),
    )
    scored_steps = [
        _make_plan_step(
            graph.nodes[state.node_id],
            edge_cost=0,
            remaining_stamina=state.remaining_stamina,
        )
    ]

    for target_step in steps[1:]:
        target_node = graph.nodes[target_step.node_id]
        door_is_active = state.has_key or not problem.locked_door

        if target_node.kind == "door" and not door_is_active:
            scored_steps.append(
                _make_plan_step(
                    target_node,
                    edge_cost=target_step.edge_cost,
                    remaining_stamina=state.remaining_stamina,
                )
            )
            return SemanticSolutionPlan(
                steps=tuple(scored_steps),
                semantic_success=False,
            )

        adjacency = graph.open_door_adjacency if door_is_active else graph.closed_door_adjacency
        edge_cost = _find_edge_cost(adjacency[state.node_id], target_node.node_id)

        if edge_cost is None or state.remaining_stamina < edge_cost:
            scored_steps.append(
                _make_plan_step(
                    target_node,
                    edge_cost=target_step.edge_cost if edge_cost is None else edge_cost,
                    remaining_stamina=state.remaining_stamina,
                )
            )
            return SemanticSolutionPlan(
                steps=tuple(scored_steps),
                semantic_success=False,
            )

        next_state = _collect_node_effects(
            problem,
            graph,
            StaminaOnlyState(
                node_id=target_node.node_id,
                remaining_stamina=state.remaining_stamina - edge_cost,
                collected_items_mask=state.collected_items_mask,
                has_key=state.has_key,
            ),
        )
        scored_steps.append(
            _make_plan_step(
                target_node,
                edge_cost=edge_cost,
                remaining_stamina=next_state.remaining_stamina,
            )
        )
        state = next_state

    if graph.nodes[state.node_id].kind != "door":
        return SemanticSolutionPlan(
            steps=tuple(scored_steps),
            semantic_success=False,
        )

    shortest_cost = (
        problem.initial_stamina
        + _get_collected_stamina_value(problem, state.collected_items_mask)
        - state.remaining_stamina
    )
    return SemanticSolutionPlan(
        steps=tuple(scored_steps),
        semantic_success=True,
        shortest_cost=shortest_cost,
        final_stamina=state.remaining_stamina,
    )


def _find_edge_cost(edges: tuple[tuple[int, int], ...], target_node_id: int) -> int | None:
    for candidate_node_id, edge_cost in edges:
        if candidate_node_id == target_node_id:
            return edge_cost

    return None


def _collect_node_effects(
    problem: StaminaOnlyHC3Problem,
    graph: StaminaOnlyGraph,
    state: StaminaOnlyState,
) -> StaminaOnlyState:
    node = graph.nodes[state.node_id]
    remaining_stamina = state.remaining_stamina
    collected_items_mask = state.collected_items_mask
    has_key = state.has_key

    if node.item_index is not None and not (collected_items_mask & (1 << node.item_index)):
        item = problem.items[node.item_index]
        collected_items_mask |= 1 << node.item_index

        if item.kind == "stamina":
            remaining_stamina += item.value
        elif item.kind == "key":
            has_key = True

    return StaminaOnlyState(
        node_id=state.node_id,
        remaining_stamina=remaining_stamina,
        collected_items_mask=collected_items_mask,
        has_key=has_key,
    )


def _apply_target_stamina_effect(
    *,
    problem: StaminaOnlyHC3Problem,
    target_node: StaminaNode,
    collected_items_mask: int,
    remaining_stamina: int,
) -> int:
    if target_node.item_index is None or collected_items_mask & (1 << target_node.item_index):
        return remaining_stamina

    item = problem.items[target_node.item_index]

    if item.kind == "stamina":
        return remaining_stamina + item.value

    return remaining_stamina


def _make_plan_step(
    node: StaminaNode,
    *,
    edge_cost: int,
    remaining_stamina: int,
) -> SemanticPlanStep:
    return SemanticPlanStep(
        node_id=node.node_id,
        position=node.position,
        kind=node.kind,
        edge_cost=edge_cost,
        remaining_stamina=remaining_stamina,
    )


def _get_collected_stamina_value(problem: StaminaOnlyHC3Problem, collected_items_mask: int) -> int:
    return sum(
        item.value
        for item_index, item in enumerate(problem.items)
        if item.kind == "stamina" and collected_items_mask & (1 << item_index)
    )


def _get_exact_dead_segment_keys(plans: tuple[SemanticSolutionPlan, ...]) -> set[tuple[int, int]]:
    return {
        (plan.steps[-2].node_id, plan.steps[-1].node_id)
        for plan in plans
        if not plan.semantic_success and len(plan.steps) >= 2
    }


def _get_attempted_segment_rates_by_key(
    plan_summaries: tuple[PlanSimulationSummary, ...],
) -> dict[tuple[int, int], list[float]]:
    segment_rates_by_key: dict[tuple[int, int], list[float]] = {}

    for plan_summary in plan_summaries:
        for segment in plan_summary.segment_summaries:
            segment_key = (segment.source_node_id, segment.target_node_id)
            segment_rates_by_key.setdefault(segment_key, []).append(segment.success_rate)

    return segment_rates_by_key


def _has_key(problem: StaminaOnlyHC3Problem, collected_items_mask: int) -> bool:
    return any(
        item.kind == "key" and collected_items_mask & (1 << item_index)
        for item_index, item in enumerate(problem.items)
    )


def _average(values: Iterable[float | int]) -> float:
    values = tuple(values)
    if not values:
        return 0.0
    return sum(values) / len(values)


def _standard_deviation(values: Iterable[float | int]) -> float:
    values = tuple(values)

    if len(values) < 2:
        return 0.0

    mean = _average(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


def _difficulty_cache_key(
    problem: StaminaOnlyHC3Problem,
    config: AgentDifficultyConfig,
) -> tuple[object, ...]:
    return (
        tuple(tuple(row) for row in problem.grid),
        problem.start,
        problem.door,
        tuple((item.kind, item.position, item.value) for item in problem.items),
        problem.initial_stamina,
        problem.locked_door,
        config,
    )


def _stable_seed(parts: tuple[object, ...]) -> int:
    digest = hashlib.sha256(repr(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")
