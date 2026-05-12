from __future__ import annotations

import unittest

from utils.hard_constraints import (
    StaminaOnlyHC3GraphCache,
    StaminaOnlyHC3Problem,
    build_stamina_only_hc3_graph,
    solve_stamina_only_hc3,
)
from utils.map_entities import ItemPlacement


def grid_from_rows(*rows: str) -> list[list[int]]:
    return [[0 if cell == "." else 1 for cell in row] for row in rows]


class StaminaOnlyHC3SolverTests(unittest.TestCase):
    def test_stamina_item_blocks_direct_transit_and_is_collected_first(self) -> None:
        problem = StaminaOnlyHC3Problem(
            grid=grid_from_rows("#######", "#.....#", "#######"),
            start=(1, 1),
            door=(1, 5),
            items=(ItemPlacement(kind="stamina", position=(1, 3), value=3),),
            initial_stamina=2,
            locked_door=False,
        )

        result = solve_stamina_only_hc3(problem)
        self.assertTrue(result.solvable)

    def test_closed_door_is_transit_cell_until_key_is_collected(self) -> None:
        problem = StaminaOnlyHC3Problem(
            grid=grid_from_rows("########", "#......#", "########"),
            start=(1, 1),
            door=(1, 3),
            items=(ItemPlacement(kind="key", position=(1, 6), value=0),),
            initial_stamina=10,
            locked_door=True,
        )

        graph, _ = build_stamina_only_hc3_graph(problem)
        start_node_id = graph.position_to_node[problem.start]
        key_node_id = graph.position_to_node[(1, 6)]
        door_node_id = graph.position_to_node[problem.door]

        closed_targets = {target_node_id for target_node_id, _ in graph.closed_door_adjacency[start_node_id]}
        open_targets = {target_node_id for target_node_id, _ in graph.open_door_adjacency[start_node_id]}

        self.assertIn(key_node_id, closed_targets)
        self.assertNotIn(door_node_id, closed_targets)
        self.assertIn(door_node_id, open_targets)

        result = solve_stamina_only_hc3(problem)
        self.assertTrue(result.solvable)

    def test_unsolvable_when_stamina_cannot_reach_any_progress_node(self) -> None:
        problem = StaminaOnlyHC3Problem(
            grid=grid_from_rows(
                "#########",
                "#.......#",
                "#########",
            ),
            start=(1, 1),
            door=(1, 7),
            items=(ItemPlacement(kind="stamina", position=(1, 4), value=2),),
            initial_stamina=2,
            locked_door=False,
        )

        result = solve_stamina_only_hc3(problem)
        self.assertFalse(result.solvable)

    def test_graph_cache_reuse(self) -> None:
        cache = StaminaOnlyHC3GraphCache()
        problem = StaminaOnlyHC3Problem(
            grid=grid_from_rows(
                "#########",
                "#.......#",
                "#.#####.#",
                "#.......#",
                "#########",
            ),
            start=(1, 1),
            door=(3, 7),
            items=(ItemPlacement(kind="stamina", position=(3, 1), value=4),),
            initial_stamina=12,
            locked_door=False,
        )

        first = solve_stamina_only_hc3(problem, cache=cache)
        second = solve_stamina_only_hc3(problem, cache=cache)

        self.assertTrue(first.solvable)
        self.assertTrue(second.solvable)
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)


if __name__ == "__main__":
    unittest.main()
