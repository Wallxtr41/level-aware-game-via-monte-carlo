"""Exact HC3 solver for the stamina-only game model.

Rules in this simplified model:
- no monsters
- no power items
- stamina items are one-shot pickups
- a closed door blocks movement like a wall
- the door becomes enterable and a success target only when it is initially
  open or the key has been collected
- reaching the door with exactly zero stamina is still a success
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from utils.map_analysis import in_bounds, is_walkable, iter_neighbors
from utils.map_entities import Grid, ItemPlacement, Position


@dataclass(frozen=True)
class StaminaOnlyHC3Problem:
    grid: Grid
    start: Position
    door: Position
    items: tuple[ItemPlacement, ...] = ()
    initial_stamina: int = 0
    locked_door: bool = False

    def topology_signature(self) -> tuple[object, ...]:
        return (
            tuple(tuple(row) for row in self.grid),
            self.start,
            self.door,
            tuple((item.kind, item.position) for item in self.items),
        )


@dataclass(frozen=True)
class StaminaNode:
    node_id: int
    position: Position
    kind: str
    item_index: int | None = None


@dataclass(frozen=True)
class StaminaOnlyGraph:
    nodes: tuple[StaminaNode, ...]
    closed_door_adjacency: dict[int, tuple[tuple[int, int], ...]]
    open_door_adjacency: dict[int, tuple[tuple[int, int], ...]]
    position_to_node: dict[Position, int]


@dataclass(frozen=True)
class StaminaOnlyState:
    node_id: int
    remaining_stamina: int
    collected_items_mask: int
    has_key: bool


@dataclass(frozen=True)
class StaminaOnlyHC3Result:
    solvable: bool
    explored_states: int
    node_count: int
    cache_hit: bool = False


@dataclass(frozen=True)
class StaminaOnlyHC3Analysis:
    solvable: bool
    explored_states: int
    node_count: int
    cache_hit: bool = False
    shortest_success_path_length: int | None = None
    best_remaining_stamina: int | None = None
    solution_steps: tuple["StaminaOnlySolutionStep", ...] = ()


@dataclass(frozen=True)
class StaminaOnlySolutionStep:
    node_id: int
    position: Position
    kind: str
    remaining_stamina: int
    edge_cost: int


@dataclass
class StaminaOnlyHC3GraphCache:
    graphs: dict[tuple[object, ...], StaminaOnlyGraph] = field(default_factory=dict)

    def get(self, problem: StaminaOnlyHC3Problem) -> StaminaOnlyGraph | None:
        return self.graphs.get(problem.topology_signature())

    def store(
        self,
        problem: StaminaOnlyHC3Problem,
        graph: StaminaOnlyGraph,
    ) -> StaminaOnlyGraph:
        self.graphs[problem.topology_signature()] = graph
        return graph


def _validate_problem(problem: StaminaOnlyHC3Problem) -> None:
    positions: dict[Position, str] = {}
    key_count = 0

    for name, position in (("start", problem.start), ("door", problem.door)):
        row, col = position

        if not in_bounds(problem.grid, row, col):
            raise ValueError(f"{name} is outside the grid.")

        if not is_walkable(problem.grid, row, col):
            raise ValueError(f"{name} must be on a walkable cell.")

        positions[position] = name

    for index, item in enumerate(problem.items):
        row, col = item.position

        if item.kind not in {"stamina", "key"}:
            raise ValueError("stamina-only HC3 accepts only stamina and key items.")

        if not in_bounds(problem.grid, row, col):
            raise ValueError(f"item {index} is outside the grid.")

        if not is_walkable(problem.grid, row, col):
            raise ValueError(f"item {index} must be on a walkable cell.")

        if item.position in positions:
            raise ValueError(f"item {index} overlaps with {positions[item.position]}.")

        positions[item.position] = f"item {index}"

        if item.kind == "key":
            key_count += 1

    if problem.locked_door and key_count != 1:
        raise ValueError("A locked door requires exactly one key item.")

    if not problem.locked_door and key_count > 1:
        raise ValueError("At most one key item is supported in this model.")


def _build_semantic_nodes(problem: StaminaOnlyHC3Problem) -> tuple[tuple[StaminaNode, ...], dict[Position, int]]:
    nodes = [StaminaNode(node_id=0, position=problem.start, kind="start")]

    for item_index, item in enumerate(problem.items):
        nodes.append(
            StaminaNode(
                node_id=len(nodes),
                position=item.position,
                kind=f"item:{item.kind}",
                item_index=item_index,
            )
        )

    nodes.append(StaminaNode(node_id=len(nodes), position=problem.door, kind="door"))
    position_to_node = {node.position: node.node_id for node in nodes}
    return tuple(nodes), position_to_node


def _compute_adjacency_for_mode(
    problem: StaminaOnlyHC3Problem,
    nodes: tuple[StaminaNode, ...],
    position_to_node: dict[Position, int],
    *,
    door_is_active: bool,
) -> dict[int, tuple[tuple[int, int], ...]]:
    active_terminal_positions = {node.position for node in nodes if node.kind != "door"}

    if door_is_active:
        active_terminal_positions.add(problem.door)

    adjacency: dict[int, tuple[tuple[int, int], ...]] = {}

    for source_node in nodes:
        queue = deque([(source_node.position, 0)])
        visited = {source_node.position}
        reachable_targets: list[tuple[int, int]] = []

        while queue:
            (row, col), distance = queue.popleft()

            for next_row, next_col in iter_neighbors(row, col):
                next_position = (next_row, next_col)

                if next_position in visited:
                    continue

                if next_position == problem.door and not door_is_active:
                    continue

                if not is_walkable(problem.grid, next_row, next_col):
                    continue

                visited.add(next_position)
                next_distance = distance + 1

                if next_position in active_terminal_positions and next_position != source_node.position:
                    reachable_targets.append((position_to_node[next_position], next_distance))
                    continue

                queue.append((next_position, next_distance))

        adjacency[source_node.node_id] = tuple(reachable_targets)

    return adjacency


def compute_reachable_edges_for_state(
    problem: StaminaOnlyHC3Problem,
    graph: StaminaOnlyGraph,
    state: StaminaOnlyState,
) -> tuple[tuple[int, int], ...]:
    source_node = graph.nodes[state.node_id]
    door_is_active = state.has_key or not problem.locked_door
    active_terminal_positions = {
        node.position
        for node in graph.nodes
        if node.item_index is not None
        and not (state.collected_items_mask & (1 << node.item_index))
    }

    if door_is_active:
        active_terminal_positions.add(problem.door)

    queue = deque([(source_node.position, 0)])
    visited = {source_node.position}
    reachable_targets: list[tuple[int, int]] = []

    while queue:
        (row, col), distance = queue.popleft()

        for next_row, next_col in iter_neighbors(row, col):
            next_position = (next_row, next_col)

            if next_position in visited:
                continue

            if next_position == problem.door and not door_is_active:
                continue

            if not is_walkable(problem.grid, next_row, next_col):
                continue

            visited.add(next_position)
            next_distance = distance + 1

            if next_position in active_terminal_positions and next_position != source_node.position:
                reachable_targets.append((graph.position_to_node[next_position], next_distance))
                continue

            queue.append((next_position, next_distance))

    return tuple(reachable_targets)


def build_stamina_only_hc3_graph(
    problem: StaminaOnlyHC3Problem,
    cache: StaminaOnlyHC3GraphCache | None = None,
) -> tuple[StaminaOnlyGraph, bool]:
    _validate_problem(problem)

    if cache is not None:
        cached_graph = cache.get(problem)

        if cached_graph is not None:
            return cached_graph, True

    nodes, position_to_node = _build_semantic_nodes(problem)
    graph = StaminaOnlyGraph(
        nodes=nodes,
        closed_door_adjacency=_compute_adjacency_for_mode(
            problem,
            nodes,
            position_to_node,
            door_is_active=False,
        ),
        open_door_adjacency=_compute_adjacency_for_mode(
            problem,
            nodes,
            position_to_node,
            door_is_active=True,
        ),
        position_to_node=position_to_node,
    )

    if cache is not None:
        cache.store(problem, graph)

    return graph, False


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


def _get_collected_stamina_value(problem: StaminaOnlyHC3Problem, collected_items_mask: int) -> int:
    total = 0

    for item_index, item in enumerate(problem.items):
        if not (collected_items_mask & (1 << item_index)):
            continue

        if item.kind == "stamina":
            total += item.value

    return total


def _state_key(state: StaminaOnlyState) -> tuple[int, int, bool, int]:
    return (
        state.node_id,
        state.collected_items_mask,
        state.has_key,
        state.remaining_stamina,
    )


def _reconstruct_solution_steps(
    graph: StaminaOnlyGraph,
    parent_by_state_key: dict[tuple[int, int, bool, int], tuple[tuple[int, int, bool, int] | None, int]],
    final_state: StaminaOnlyState,
) -> tuple[StaminaOnlySolutionStep, ...]:
    steps: list[StaminaOnlySolutionStep] = []
    current_key = _state_key(final_state)

    while True:
        node = graph.nodes[current_key[0]]
        parent_key, edge_cost = parent_by_state_key[current_key]
        steps.append(
            StaminaOnlySolutionStep(
                node_id=node.node_id,
                position=node.position,
                kind=node.kind,
                remaining_stamina=current_key[3],
                edge_cost=edge_cost,
            )
        )

        if parent_key is None:
            break

        current_key = parent_key

    steps.reverse()
    return tuple(steps)


def _analyze_stamina_only_search(
    problem: StaminaOnlyHC3Problem,
    cache: StaminaOnlyHC3GraphCache | None = None,
    *,
    stop_on_first_success: bool,
) -> StaminaOnlyHC3Analysis:
    graph, cache_hit = build_stamina_only_hc3_graph(problem, cache=cache)
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

    frontier = deque([start_state])
    best_stamina_by_signature: dict[tuple[int, int, bool], int] = {
        (
            start_state.node_id,
            start_state.collected_items_mask,
            start_state.has_key,
        ): start_state.remaining_stamina
    }
    parent_by_state_key: dict[tuple[int, int, bool, int], tuple[tuple[int, int, bool, int] | None, int]] = {
        _state_key(start_state): (None, 0)
    }
    explored_states = 0
    shortest_success_path_length: int | None = None
    best_remaining_stamina: int | None = None
    best_solution_steps: tuple[StaminaOnlySolutionStep, ...] = ()

    while frontier:
        current_state = frontier.popleft()
        explored_states += 1

        for target_node_id, edge_cost in compute_reachable_edges_for_state(problem, graph, current_state):
            next_stamina = current_state.remaining_stamina - edge_cost

            if next_stamina < 0:
                continue

            next_state = _collect_node_effects(
                problem,
                graph,
                StaminaOnlyState(
                    node_id=target_node_id,
                    remaining_stamina=next_stamina,
                    collected_items_mask=current_state.collected_items_mask,
                    has_key=current_state.has_key,
                ),
            )

            target_node = graph.nodes[target_node_id]

            if target_node.kind == "door" and next_state.remaining_stamina >= 0:
                collected_stamina_value = _get_collected_stamina_value(
                    problem,
                    next_state.collected_items_mask,
                )
                success_path_length = (
                    problem.initial_stamina
                    + collected_stamina_value
                    - next_state.remaining_stamina
                )
                shortest_success_path_length = (
                    success_path_length
                    if shortest_success_path_length is None
                    else min(shortest_success_path_length, success_path_length)
                )
                best_remaining_stamina = (
                    next_state.remaining_stamina
                    if best_remaining_stamina is None
                    else max(best_remaining_stamina, next_state.remaining_stamina)
                )
                current_state_key = _state_key(current_state)
                next_state_key = _state_key(next_state)
                previous_parent = parent_by_state_key.get(next_state_key)
                parent_by_state_key[next_state_key] = (current_state_key, edge_cost)
                solution_steps = _reconstruct_solution_steps(
                    graph,
                    parent_by_state_key,
                    next_state,
                )

                if (
                    not best_solution_steps
                    or success_path_length == shortest_success_path_length
                    and next_state.remaining_stamina >= (best_remaining_stamina or next_state.remaining_stamina)
                ):
                    best_solution_steps = solution_steps

                if stop_on_first_success:
                    return StaminaOnlyHC3Analysis(
                        solvable=True,
                        explored_states=explored_states,
                        node_count=len(graph.nodes),
                        cache_hit=cache_hit,
                        shortest_success_path_length=shortest_success_path_length,
                        best_remaining_stamina=best_remaining_stamina,
                        solution_steps=solution_steps,
                    )

                if previous_parent is None:
                    parent_by_state_key.pop(next_state_key, None)
                else:
                    parent_by_state_key[next_state_key] = previous_parent

                continue

            signature = (
                next_state.node_id,
                next_state.collected_items_mask,
                next_state.has_key,
            )
            best_known_stamina = best_stamina_by_signature.get(signature)

            if best_known_stamina is not None and best_known_stamina >= next_state.remaining_stamina:
                continue

            best_stamina_by_signature[signature] = next_state.remaining_stamina
            parent_by_state_key[_state_key(next_state)] = (_state_key(current_state), edge_cost)
            frontier.append(next_state)

    return StaminaOnlyHC3Analysis(
        solvable=shortest_success_path_length is not None,
        explored_states=explored_states,
        node_count=len(graph.nodes),
        cache_hit=cache_hit,
        shortest_success_path_length=shortest_success_path_length,
        best_remaining_stamina=best_remaining_stamina,
        solution_steps=best_solution_steps,
    )


def solve_stamina_only_hc3(
    problem: StaminaOnlyHC3Problem,
    cache: StaminaOnlyHC3GraphCache | None = None,
) -> StaminaOnlyHC3Result:
    analysis = _analyze_stamina_only_search(
        problem,
        cache=cache,
        stop_on_first_success=True,
    )
    return StaminaOnlyHC3Result(
        solvable=analysis.solvable,
        explored_states=analysis.explored_states,
        node_count=analysis.node_count,
        cache_hit=analysis.cache_hit,
    )


def analyze_stamina_only_hc3(
    problem: StaminaOnlyHC3Problem,
    cache: StaminaOnlyHC3GraphCache | None = None,
) -> StaminaOnlyHC3Analysis:
    return _analyze_stamina_only_search(
        problem,
        cache=cache,
        stop_on_first_success=False,
    )


def is_stamina_only_hc3_satisfied(
    problem: StaminaOnlyHC3Problem,
    cache: StaminaOnlyHC3GraphCache | None = None,
) -> bool:
    return solve_stamina_only_hc3(problem, cache=cache).solvable
