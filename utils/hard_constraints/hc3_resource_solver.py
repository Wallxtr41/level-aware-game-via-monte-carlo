"""Hard Constraint 3: exact resource-aware solvability.

HC3 is satisfied exactly when there exists at least one valid playthrough from
the start cell to the door under the full resource rules.

Formal transition model
-----------------------
State:
    (node_id, stamina, strength, has_key, collected_items_mask,
     defeated_monsters_mask)

Move semantics:
1. Traverse one compressed graph edge, paying its stamina cost.
2. Defeat every undefeated corridor monster on that edge.
3. Enter the destination node and resolve its monster, item, or door rule.
4. Accept the state only if the player is still alive after the transition.

The search is exact because every future-relevant fact is part of the state:
position, remaining resources, collected items, defeated monsters, and key
ownership. A label is pruned only when another label at the same abstract state
has both at least as much stamina and at least as much strength.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from utils.map_analysis import in_bounds, is_walkable, iter_neighbors
from utils.map_entities import Grid, ItemPlacement, MonsterPlacement, Position


@dataclass(frozen=True)
class HC3Problem:
    grid: Grid
    start: Position
    door: Position
    items: tuple[ItemPlacement, ...] = ()
    monsters: tuple[MonsterPlacement, ...] = ()
    initial_stamina: int = 0
    initial_strength: int = 0
    locked_door: bool = False
    minimum_final_stamina: int = 0
    minimum_final_strength: int = 0

    def topology_signature(self) -> tuple[object, ...]:
        return (
            tuple(tuple(row) for row in self.grid),
            self.start,
            self.door,
            tuple((item.kind, item.position) for item in self.items),
            tuple(monster.position for monster in self.monsters),
        )


@dataclass(frozen=True)
class GraphNode:
    node_id: int
    position: Position
    kind: str
    item_index: int | None = None
    monster_index: int | None = None


@dataclass(frozen=True)
class GraphEdge:
    edge_id: int
    start_node: int
    end_node: int
    steps: int
    corridor_monster_indices: tuple[int, ...] = ()


@dataclass(frozen=True)
class HC3Graph:
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    adjacency: dict[int, tuple[int, ...]]
    position_to_node: dict[Position, int]


@dataclass(frozen=True)
class SolverLabel:
    node_id: int
    stamina: int
    strength: int
    has_key: bool
    collected_items_mask: int
    defeated_monsters_mask: int


@dataclass(frozen=True)
class HC3Result:
    solvable: bool
    explored_labels: int
    graph_node_count: int
    graph_edge_count: int
    cache_hit: bool = False


@dataclass
class HC3GraphCache:
    graphs: dict[tuple[object, ...], HC3Graph] = field(default_factory=dict)

    def get(self, problem: HC3Problem) -> HC3Graph | None:
        return self.graphs.get(problem.topology_signature())

    def store(self, problem: HC3Problem, graph: HC3Graph) -> HC3Graph:
        self.graphs[problem.topology_signature()] = graph
        return graph


def _is_turn_cell(grid: Grid, row: int, col: int) -> bool:
    neighbors = [
        (next_row, next_col)
        for next_row, next_col in iter_neighbors(row, col)
        if is_walkable(grid, next_row, next_col)
    ]

    if len(neighbors) != 2:
        return False

    same_row = neighbors[0][0] == neighbors[1][0]
    same_col = neighbors[0][1] == neighbors[1][1]
    return not (same_row or same_col)


def _validate_problem(problem: HC3Problem) -> None:
    positions: dict[Position, str] = {}
    key_count = 0

    for name, position in (("start", problem.start), ("door", problem.door)):
        row, col = position

        if not in_bounds(problem.grid, row, col):
            raise ValueError(f"{name} is outside the grid.")

        if not is_walkable(problem.grid, row, col):
            raise ValueError(f"{name} must be placed on a walkable cell.")

        positions[position] = name

    for index, item in enumerate(problem.items):
        row, col = item.position

        if not in_bounds(problem.grid, row, col):
            raise ValueError(f"item {index} is outside the grid.")

        if not is_walkable(problem.grid, row, col):
            raise ValueError(f"item {index} must be placed on a walkable cell.")

        if item.position in positions:
            raise ValueError(f"item {index} overlaps with {positions[item.position]}.")

        positions[item.position] = f"item {index}"

        if item.kind == "key":
            key_count += 1

    for index, monster in enumerate(problem.monsters):
        row, col = monster.position

        if not in_bounds(problem.grid, row, col):
            raise ValueError(f"monster {index} is outside the grid.")

        if not is_walkable(problem.grid, row, col):
            raise ValueError(f"monster {index} must be placed on a walkable cell.")

        if monster.position in positions:
            raise ValueError(f"monster {index} overlaps with {positions[monster.position]}.")

        positions[monster.position] = f"monster {index}"

    if problem.locked_door and key_count != 1:
        raise ValueError("A locked door requires exactly one key item.")


def build_hc3_graph(
    problem: HC3Problem,
    cache: HC3GraphCache | None = None,
) -> tuple[HC3Graph, bool]:
    _validate_problem(problem)

    if cache is not None:
        cached_graph = cache.get(problem)

        if cached_graph is not None:
            return cached_graph, True

    item_positions = {item.position: index for index, item in enumerate(problem.items)}
    monster_positions = {monster.position: index for index, monster in enumerate(problem.monsters)}
    node_positions: list[Position] = []

    for row_index, row in enumerate(problem.grid):
        for col_index, cell in enumerate(row):
            if cell != 0:
                continue

            position = (row_index, col_index)
            walkable_neighbors = sum(
                is_walkable(problem.grid, next_row, next_col)
                for next_row, next_col in iter_neighbors(row_index, col_index)
            )
            is_semantic_node = (
                position == problem.start
                or position == problem.door
                or position in item_positions
            )
            is_monster_node = position in monster_positions and (
                walkable_neighbors != 2 or _is_turn_cell(problem.grid, row_index, col_index)
            )
            is_structural_node = walkable_neighbors != 2 or _is_turn_cell(
                problem.grid,
                row_index,
                col_index,
            )

            if is_semantic_node or is_monster_node or is_structural_node:
                node_positions.append(position)

    position_to_node = {
        position: node_id
        for node_id, position in enumerate(node_positions)
    }

    nodes: list[GraphNode] = []

    for node_id, position in enumerate(node_positions):
        item_index = item_positions.get(position)
        monster_index = monster_positions.get(position)
        kind = "junction"

        if position == problem.start:
            kind = "start"
        elif position == problem.door:
            kind = "door"
        elif item_index is not None:
            kind = f"item:{problem.items[item_index].kind}"
        elif monster_index is not None:
            kind = "monster"
        else:
            row, col = position
            walkable_neighbors = sum(
                is_walkable(problem.grid, next_row, next_col)
                for next_row, next_col in iter_neighbors(row, col)
            )

            if walkable_neighbors <= 1:
                kind = "dead_end"
            elif _is_turn_cell(problem.grid, row, col):
                kind = "turn"

        nodes.append(
            GraphNode(
                node_id=node_id,
                position=position,
                kind=kind,
                item_index=item_index,
                monster_index=monster_index,
            )
        )

    visited_steps: set[tuple[Position, Position]] = set()
    edges: list[GraphEdge] = []
    adjacency: dict[int, list[int]] = {node.node_id: [] for node in nodes}

    for node in nodes:
        for neighbor in iter_neighbors(*node.position):
            if not is_walkable(problem.grid, neighbor[0], neighbor[1]):
                continue

            if (node.position, neighbor) in visited_steps:
                continue

            path_positions = [neighbor]
            previous = node.position
            current = neighbor

            while current not in position_to_node:
                next_positions = [
                    next_position
                    for next_position in iter_neighbors(*current)
                    if is_walkable(problem.grid, next_position[0], next_position[1])
                    and next_position != previous
                ]

                if len(next_positions) != 1:
                    raise ValueError(
                        "Graph compression expected a straight corridor but found "
                        "an ambiguous interior cell."
                    )

                previous, current = current, next_positions[0]
                path_positions.append(current)

            full_path = [node.position, *path_positions]

            for index in range(len(full_path) - 1):
                step_start = full_path[index]
                step_end = full_path[index + 1]
                visited_steps.add((step_start, step_end))
                visited_steps.add((step_end, step_start))

            corridor_positions = path_positions[:-1]
            corridor_monster_indices = tuple(
                monster_positions[position]
                for position in corridor_positions
                if position in monster_positions
            )
            other_node_id = position_to_node[current]
            edge_id = len(edges)
            edge = GraphEdge(
                edge_id=edge_id,
                start_node=node.node_id,
                end_node=other_node_id,
                steps=len(path_positions),
                corridor_monster_indices=corridor_monster_indices,
            )
            edges.append(edge)
            adjacency[node.node_id].append(edge_id)
            adjacency[other_node_id].append(edge_id)

    graph = HC3Graph(
        nodes=tuple(nodes),
        edges=tuple(edges),
        adjacency={node_id: tuple(edge_ids) for node_id, edge_ids in adjacency.items()},
        position_to_node=position_to_node,
    )

    if cache is not None:
        cache.store(problem, graph)

    return graph, False


def _monster_cost(problem: HC3Problem, monster_indices: tuple[int, ...], defeated_mask: int) -> int:
    total_cost = 0

    for monster_index in monster_indices:
        if defeated_mask & (1 << monster_index):
            continue

        total_cost += problem.monsters[monster_index].strength

    return total_cost


def _apply_node_effects(
    problem: HC3Problem,
    graph: HC3Graph,
    label: SolverLabel,
) -> tuple[SolverLabel | None, bool]:
    node = graph.nodes[label.node_id]
    stamina = label.stamina
    strength = label.strength
    has_key = label.has_key
    collected_items_mask = label.collected_items_mask
    defeated_monsters_mask = label.defeated_monsters_mask

    if node.monster_index is not None and not (defeated_monsters_mask & (1 << node.monster_index)):
        monster_strength = problem.monsters[node.monster_index].strength

        if strength < monster_strength:
            return None, False

        strength -= monster_strength
        defeated_monsters_mask |= 1 << node.monster_index

    if node.item_index is not None and not (collected_items_mask & (1 << node.item_index)):
        item = problem.items[node.item_index]
        collected_items_mask |= 1 << node.item_index

        if item.kind == "stamina":
            stamina += item.value
        elif item.kind == "power":
            strength += item.value
        elif item.kind == "key":
            has_key = True

    if node.kind == "door":
        if problem.locked_door and not has_key:
            return None, False

        success = (
            stamina >= problem.minimum_final_stamina
            and strength >= problem.minimum_final_strength
        )
        next_label = SolverLabel(
            node_id=label.node_id,
            stamina=stamina,
            strength=strength,
            has_key=has_key,
            collected_items_mask=collected_items_mask,
            defeated_monsters_mask=defeated_monsters_mask,
        )
        return next_label, success

    if stamina <= 0:
        return None, False

    next_label = SolverLabel(
        node_id=label.node_id,
        stamina=stamina,
        strength=strength,
        has_key=has_key,
        collected_items_mask=collected_items_mask,
        defeated_monsters_mask=defeated_monsters_mask,
    )
    return next_label, False


def _transition_label(
    problem: HC3Problem,
    graph: HC3Graph,
    label: SolverLabel,
    edge: GraphEdge,
) -> tuple[SolverLabel | None, bool]:
    other_node_id = edge.end_node if edge.start_node == label.node_id else edge.start_node
    remaining_stamina = label.stamina - edge.steps

    if remaining_stamina < 0:
        return None, False

    corridor_cost = _monster_cost(
        problem,
        edge.corridor_monster_indices,
        label.defeated_monsters_mask,
    )

    if label.strength < corridor_cost:
        return None, False

    defeated_monsters_mask = label.defeated_monsters_mask

    for monster_index in edge.corridor_monster_indices:
        defeated_monsters_mask |= 1 << monster_index

    traversed_label = SolverLabel(
        node_id=other_node_id,
        stamina=remaining_stamina,
        strength=label.strength - corridor_cost,
        has_key=label.has_key,
        collected_items_mask=label.collected_items_mask,
        defeated_monsters_mask=defeated_monsters_mask,
    )
    return _apply_node_effects(problem, graph, traversed_label)


def _dominates(left: SolverLabel, right: SolverLabel) -> bool:
    return (
        left.stamina >= right.stamina
        and left.strength >= right.strength
        and (left.stamina > right.stamina or left.strength > right.strength)
    )


def solve_hc3(
    problem: HC3Problem,
    cache: HC3GraphCache | None = None,
) -> HC3Result:
    graph, cache_hit = build_hc3_graph(problem, cache=cache)
    start_node_id = graph.position_to_node[problem.start]
    initial_label, success = _apply_node_effects(
        problem,
        graph,
        SolverLabel(
            node_id=start_node_id,
            stamina=problem.initial_stamina,
            strength=problem.initial_strength,
            has_key=False,
            collected_items_mask=0,
            defeated_monsters_mask=0,
        ),
    )

    if initial_label is None:
        return HC3Result(
            solvable=False,
            explored_labels=0,
            graph_node_count=len(graph.nodes),
            graph_edge_count=len(graph.edges),
            cache_hit=cache_hit,
        )

    if success:
        return HC3Result(
            solvable=True,
            explored_labels=1,
            graph_node_count=len(graph.nodes),
            graph_edge_count=len(graph.edges),
            cache_hit=cache_hit,
        )

    frontier = deque([initial_label])
    labels_by_signature: dict[tuple[int, bool, int, int], list[SolverLabel]] = {
        (
            initial_label.node_id,
            initial_label.has_key,
            initial_label.collected_items_mask,
            initial_label.defeated_monsters_mask,
        ): [initial_label]
    }
    explored_labels = 0

    while frontier:
        current_label = frontier.popleft()
        explored_labels += 1

        for edge_id in graph.adjacency[current_label.node_id]:
            candidate_label, success = _transition_label(
                problem,
                graph,
                current_label,
                graph.edges[edge_id],
            )

            if candidate_label is None:
                continue

            if success:
                return HC3Result(
                    solvable=True,
                    explored_labels=explored_labels,
                    graph_node_count=len(graph.nodes),
                    graph_edge_count=len(graph.edges),
                    cache_hit=cache_hit,
                )

            signature = (
                candidate_label.node_id,
                candidate_label.has_key,
                candidate_label.collected_items_mask,
                candidate_label.defeated_monsters_mask,
            )
            existing_labels = labels_by_signature.setdefault(signature, [])

            if any(_dominates(existing_label, candidate_label) for existing_label in existing_labels):
                continue

            surviving_labels = [
                existing_label
                for existing_label in existing_labels
                if not _dominates(candidate_label, existing_label)
            ]
            surviving_labels.append(candidate_label)
            labels_by_signature[signature] = surviving_labels
            frontier.append(candidate_label)

    return HC3Result(
        solvable=False,
        explored_labels=explored_labels,
        graph_node_count=len(graph.nodes),
        graph_edge_count=len(graph.edges),
        cache_hit=cache_hit,
    )


def is_hc3_satisfied(
    problem: HC3Problem,
    cache: HC3GraphCache | None = None,
) -> bool:
    return solve_hc3(problem, cache=cache).solvable
