from __future__ import annotations

import random
import unittest

import baseline_pipeline as bp


class InitialStaminaFormulaTests(unittest.TestCase):
    def test_auto_initial_stamina_increases_with_difficulty_without_noise(self) -> None:
        original_noise_scale = bp.INITIAL_STAMINA_NOISE_STD_SCALE

        try:
            bp.INITIAL_STAMINA_NOISE_STD_SCALE = 0.0
            easy_stamina = bp.calculate_auto_initial_stamina(
                grid_width=15,
                grid_height=15,
                target_agent_difficulty=0.0,
                rng=random.Random(1),
            )
            hard_stamina = bp.calculate_auto_initial_stamina(
                grid_width=15,
                grid_height=15,
                target_agent_difficulty=1.0,
                rng=random.Random(1),
            )
        finally:
            bp.INITIAL_STAMINA_NOISE_STD_SCALE = original_noise_scale

        self.assertLess(easy_stamina, hard_stamina)

    def test_auto_initial_stamina_noise_is_seeded(self) -> None:
        first_stamina = bp.calculate_auto_initial_stamina(
            grid_width=15,
            grid_height=15,
            target_agent_difficulty=0.75,
            rng=random.Random(123),
        )
        second_stamina = bp.calculate_auto_initial_stamina(
            grid_width=15,
            grid_height=15,
            target_agent_difficulty=0.75,
            rng=random.Random(123),
        )

        self.assertEqual(first_stamina, second_stamina)

    def test_initial_on_path_stamina_count_follows_usage_target(self) -> None:
        original_difficulty = bp.TARGET_AGENT_DIFFICULTY
        original_usage_target = bp.TARGET_STAMINA_USAGE_RATE

        try:
            bp.TARGET_STAMINA_USAGE_RATE = None
            bp.TARGET_AGENT_DIFFICULTY = 0.1
            self.assertEqual(
                bp._target_on_path_stamina_count(("stamina", "stamina", "key")),
                0,
            )

            bp.TARGET_AGENT_DIFFICULTY = 0.5
            self.assertEqual(
                bp._target_on_path_stamina_count(("stamina", "stamina", "key")),
                1,
            )

            bp.TARGET_STAMINA_USAGE_RATE = 1.0
            self.assertEqual(
                bp._target_on_path_stamina_count(("stamina", "stamina", "key")),
                2,
            )
        finally:
            bp.TARGET_AGENT_DIFFICULTY = original_difficulty
            bp.TARGET_STAMINA_USAGE_RATE = original_usage_target

    def test_initial_door_candidates_include_near_positions(self) -> None:
        original_difficulty = bp.TARGET_AGENT_DIFFICULTY

        try:
            bp.TARGET_AGENT_DIFFICULTY = 0.1
            grid = [
                [1, 1, 1, 1, 1, 1, 1],
                [1, 0, 0, 0, 0, 0, 1],
                [1, 1, 1, 1, 1, 1, 1],
            ]
            candidates = bp.choose_stamina_mode_door_candidates(
                grid=grid,
                start=(1, 1),
                max_path_length=4,
                initial_stamina=10,
                item_kinds=("key",),
                limit=4,
            )
        finally:
            bp.TARGET_AGENT_DIFFICULTY = original_difficulty

        self.assertIn((1, 2), candidates)
        self.assertLessEqual(len(candidates), 4)

    def test_initial_item_candidates_avoid_start_when_possible(self) -> None:
        original_min_distance_scale = bp.INITIAL_ITEM_MIN_START_DISTANCE_SCALE

        try:
            bp.INITIAL_ITEM_MIN_START_DISTANCE_SCALE = 0.25
            grid = [
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            ]
            path = [(1, col) for col in range(1, 10)]
            candidates = bp.construct_stamina_mode_item_candidates(
                grid=grid,
                path=path,
                initial_stamina=20,
                item_kinds=("key",),
                rng=random.Random(1),
            )
            start_distances = bp.bfs_distances(grid, path[0])
            minimum_distance = bp._initial_min_item_start_distance(grid)
        finally:
            bp.INITIAL_ITEM_MIN_START_DISTANCE_SCALE = original_min_distance_scale

        self.assertTrue(candidates)

        for candidate in candidates:
            for item in candidate:
                self.assertGreaterEqual(start_distances[item.position], minimum_distance)


if __name__ == "__main__":
    unittest.main()
