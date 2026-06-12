from __future__ import annotations

import random
import unittest

import baseline_pipeline as bp
from utils import game_config
from utils.map_entities import get_default_item_value


class InitialStaminaFormulaTests(unittest.TestCase):
    def test_difficulty_stamina_config_is_clamped(self) -> None:
        config = game_config.clamp_difficulty_stamina_config(
            game_config.DifficultyStaminaConfig(
                target_agent_difficulty=2.0,
                player_vision_radius=99,
                grid_width=10,
                grid_height=200,
                door_requires_key=True,
                stamina_item_count=10,
                stamina_item_value=999,
            )
        )

        self.assertEqual(config.target_agent_difficulty, 1.0)
        self.assertEqual(config.player_vision_radius, game_config.MAX_PLAYER_VISION_RADIUS)
        self.assertEqual(config.grid_width, 11)
        self.assertEqual(config.grid_height, 25)
        self.assertEqual(config.stamina_item_count, 3)
        self.assertEqual(config.stamina_item_value, game_config.MAX_STAMINA_ITEM_VALUE)

    def test_baseline_applies_difficulty_stamina_config(self) -> None:
        original_config = game_config.get_difficulty_stamina_config()

        try:
            applied_config = bp.apply_difficulty_stamina_config(
                game_config.DifficultyStaminaConfig(
                    target_agent_difficulty=0.7,
                    player_vision_radius=3,
                    grid_width=12,
                    grid_height=14,
                    door_requires_key=False,
                    stamina_item_count=3,
                    stamina_item_value=22,
                )
            )

            self.assertEqual(applied_config.grid_width, 13)
            self.assertEqual(applied_config.grid_height, 15)
            self.assertEqual(bp.GRID_WIDTH, 13)
            self.assertEqual(bp.GRID_HEIGHT, 15)
            self.assertEqual(bp.TARGET_AGENT_DIFFICULTY, 0.7)
            self.assertEqual(bp.get_mode_config().item_kinds, ("stamina", "stamina", "stamina"))
            self.assertFalse(bp.get_mode_config().locked_door)
            self.assertEqual(get_default_item_value("stamina"), 22)
        finally:
            bp.apply_difficulty_stamina_config(original_config)

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
                [1, 1, 1, 1, 1, 1, 1, 1],
                [1, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 1],
                [1, 1, 1, 1, 1, 1, 1, 1],
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

    def test_door_partitioning_is_rejected(self) -> None:
        grid = [
            [1, 1, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 1],
            [1, 1, 1, 1, 1, 1, 1],
        ]

        self.assertFalse(bp.is_door_non_partitioning(grid, (1, 1), (1, 3)))
        self.assertTrue(bp.is_door_non_partitioning(grid, (1, 1), (1, 5)))

    def test_door_with_alternate_route_is_allowed(self) -> None:
        grid = [
            [1, 1, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 1],
            [1, 1, 1, 1, 1, 1, 1],
        ]

        self.assertTrue(bp.is_door_non_partitioning(grid, (1, 1), (1, 3)))

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
