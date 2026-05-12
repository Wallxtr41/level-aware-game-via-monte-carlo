from __future__ import annotations

import unittest

from utils.hard_constraints import HC3GraphCache, HC3Problem, solve_hc3
from utils.map_entities import ItemPlacement, MonsterPlacement


def grid_from_rows(*rows: str) -> list[list[int]]:
    return [[0 if cell == "." else 1 for cell in row] for row in rows]


class HC3SolverTests(unittest.TestCase):
    def test_locked_door_requires_reachable_key(self) -> None:
        problem = HC3Problem(
            grid=grid_from_rows(
                "########",
                "#......#",
                "#.####.#",
                "#......#",
                "########",
            ),
            start=(1, 1),
            door=(1, 6),
            items=(ItemPlacement(kind="key", position=(3, 1), value=0),),
            initial_stamina=20,
            locked_door=True,
        )

        result = solve_hc3(problem)
        self.assertTrue(result.solvable)

    def test_monster_blocks_map_without_enough_strength(self) -> None:
        problem = HC3Problem(
            grid=grid_from_rows(
                "#######",
                "#.....#",
                "#######",
            ),
            start=(1, 1),
            door=(1, 5),
            monsters=(MonsterPlacement(position=(1, 3), strength=2),),
            initial_stamina=10,
            initial_strength=1,
        )

        result = solve_hc3(problem)
        self.assertFalse(result.solvable)

    def test_power_pickup_enables_corridor_monster_path(self) -> None:
        problem = HC3Problem(
            grid=grid_from_rows(
                "#########",
                "#.......#",
                "#.#####.#",
                "#.......#",
                "#########",
            ),
            start=(1, 1),
            door=(1, 7),
            items=(ItemPlacement(kind="power", position=(3, 1), value=2),),
            monsters=(MonsterPlacement(position=(1, 4), strength=2),),
            initial_stamina=20,
            initial_strength=0,
        )

        result = solve_hc3(problem)
        self.assertTrue(result.solvable)

    def test_graph_cache_reuses_topology(self) -> None:
        cache = HC3GraphCache()
        problem = HC3Problem(
            grid=grid_from_rows(
                "#######",
                "#.....#",
                "#.###.#",
                "#.....#",
                "#######",
            ),
            start=(1, 1),
            door=(3, 5),
            items=(ItemPlacement(kind="stamina", position=(3, 1), value=4),),
            initial_stamina=12,
        )

        first = solve_hc3(problem, cache=cache)
        second = solve_hc3(problem, cache=cache)

        self.assertTrue(first.solvable)
        self.assertTrue(second.solvable)
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)


if __name__ == "__main__":
    unittest.main()
