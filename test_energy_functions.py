from __future__ import annotations

from dataclasses import dataclass
import math
import unittest

from utils.agent_difficulty import AgentDifficultyConfig
from utils.energy_functions import stamina_agent_difficulty_energy_breakdown
from utils.map_entities import ItemPlacement


@dataclass(frozen=True)
class DummyState:
    grid: list[list[int]]
    start: tuple[int, int]
    door: tuple[int, int]
    items: tuple[object, ...]
    initial_stamina: int
    locked_door: bool


def grid_from_rows(*rows: str) -> list[list[int]]:
    return [[0 if cell == "." else 1 for cell in row] for row in rows]


class EnergyFunctionTests(unittest.TestCase):
    def test_agent_final_stamina_term_uses_success_weighted_average(self) -> None:
        state = DummyState(
            grid=grid_from_rows(
                "#######",
                "#.....#",
                "#######",
            ),
            start=(1, 1),
            door=(1, 5),
            items=(),
            initial_stamina=10,
            locked_door=False,
        )

        breakdown = stamina_agent_difficulty_energy_breakdown(
            state=state,
            target_agent_difficulty=0.75,
            difficulty_weight=0.0,
            segment_target_weight=0.0,
            segment_balance_weight=0.0,
            dead_segment_weight=0.0,
            stamina_usage_weight=0.0,
            final_stamina_weight=10.0,
            final_stamina_target_factor=0.8,
            spacing_weight=0.0,
            coverage_weight=0.0,
            branching_weight=0.0,
            agent_config=AgentDifficultyConfig(agents_per_segment=10, random_seed=1),
        )

        self.assertEqual(breakdown.remaining_stamina_target, 2.0)
        self.assertEqual(breakdown.remaining_stamina_actual, 6.0)
        self.assertAlmostEqual(breakdown.remaining_stamina_score, 0.4)
        self.assertAlmostEqual(breakdown.remaining_stamina_term, 4.0)
        self.assertAlmostEqual(breakdown.total_energy, 4.0)

    def test_spacing_term_uses_start_key_door_shortest_path_distances(self) -> None:
        state = DummyState(
            grid=grid_from_rows(
                "#######",
                "#.....#",
                "#######",
            ),
            start=(1, 1),
            door=(1, 5),
            items=(ItemPlacement(kind="key", position=(1, 3), value=0),),
            initial_stamina=10,
            locked_door=False,
        )

        breakdown = stamina_agent_difficulty_energy_breakdown(
            state=state,
            target_agent_difficulty=0.5,
            difficulty_weight=0.0,
            segment_target_weight=0.0,
            segment_balance_weight=0.0,
            dead_segment_weight=0.0,
            stamina_usage_weight=0.0,
            final_stamina_weight=0.0,
            spacing_weight=10.0,
            spacing_target_scale=1.5,
            agent_config=AgentDifficultyConfig(agents_per_segment=10, random_seed=2),
        )

        expected_actual = (2 + 2) / 2
        expected_target = 1.5 * math.sqrt(21) * 0.75
        expected_score = (abs(expected_target - expected_actual) / max(1.0, expected_target)) ** 2

        self.assertAlmostEqual(breakdown.spacing_actual, expected_actual)
        self.assertAlmostEqual(breakdown.spacing_target, expected_target)
        self.assertAlmostEqual(breakdown.spacing_score, expected_score)
        self.assertAlmostEqual(breakdown.spacing_term, 10.0 * expected_score)

    def test_spacing_term_blocks_locked_door_before_key(self) -> None:
        state = DummyState(
            grid=grid_from_rows(
                "########",
                "#......#",
                "#......#",
                "########",
            ),
            start=(1, 1),
            door=(1, 3),
            items=(ItemPlacement(kind="key", position=(1, 5), value=0),),
            initial_stamina=20,
            locked_door=True,
        )

        breakdown = stamina_agent_difficulty_energy_breakdown(
            state=state,
            target_agent_difficulty=0.5,
            difficulty_weight=0.0,
            segment_target_weight=0.0,
            segment_balance_weight=0.0,
            dead_segment_weight=0.0,
            stamina_usage_weight=0.0,
            final_stamina_weight=0.0,
            spacing_weight=10.0,
            spacing_target_scale=1.5,
            agent_config=AgentDifficultyConfig(agents_per_segment=10, random_seed=22),
        )

        self.assertAlmostEqual(breakdown.spacing_actual, (6 + 2) / 2)

    def test_segment_target_term_penalizes_segments_far_from_target_success(self) -> None:
        state = DummyState(
            grid=grid_from_rows(
                "#######",
                "#.....#",
                "#######",
            ),
            start=(1, 1),
            door=(1, 5),
            items=(),
            initial_stamina=10,
            locked_door=False,
        )

        breakdown = stamina_agent_difficulty_energy_breakdown(
            state=state,
            target_agent_difficulty=0.75,
            difficulty_weight=0.0,
            segment_target_weight=4.0,
            segment_balance_weight=0.0,
            dead_segment_weight=0.0,
            stamina_usage_weight=0.0,
            final_stamina_weight=0.0,
            spacing_weight=0.0,
            coverage_weight=0.0,
            branching_weight=0.0,
            agent_config=AgentDifficultyConfig(agents_per_segment=10, random_seed=3),
        )

        self.assertAlmostEqual(breakdown.segment_success_target, 0.25)
        self.assertAlmostEqual(breakdown.segment_target_score, 0.75)
        self.assertAlmostEqual(breakdown.segment_target_term, 3.0)
        self.assertAlmostEqual(breakdown.total_energy, 3.0)

    def test_stamina_usage_term_penalizes_maps_completable_without_stamina_items(self) -> None:
        state = DummyState(
            grid=grid_from_rows(
                "#######",
                "#.....#",
                "#.###.#",
                "#.....#",
                "#######",
            ),
            start=(1, 1),
            door=(1, 5),
            items=(ItemPlacement(kind="stamina", position=(3, 1), value=4),),
            initial_stamina=20,
            locked_door=False,
        )

        breakdown = stamina_agent_difficulty_energy_breakdown(
            state=state,
            target_agent_difficulty=0.5,
            difficulty_weight=0.0,
            segment_target_weight=0.0,
            segment_balance_weight=0.0,
            dead_segment_weight=0.0,
            stamina_usage_weight=8.0,
            target_stamina_usage_rate=1.0,
            final_stamina_weight=0.0,
            spacing_weight=0.0,
            coverage_weight=0.0,
            branching_weight=0.0,
            agent_config=AgentDifficultyConfig(agents_per_segment=10, random_seed=4),
        )

        # initial_stamina=20 ile item'siz direkt plan da gecerli oldugu icin
        # minimum viable usage 0'dir ve hedef 1.0'a uzaklik tam ceza uretir.
        self.assertAlmostEqual(breakdown.stamina_usage_target, 1.0)
        self.assertAlmostEqual(breakdown.stamina_usage_actual, 0.0)
        self.assertAlmostEqual(breakdown.stamina_usage_score, 1.0)
        self.assertAlmostEqual(breakdown.stamina_usage_term, 8.0)
        self.assertAlmostEqual(breakdown.total_energy, 8.0)

    def test_stamina_usage_uses_minimum_viable_collection_ratio(self) -> None:
        grid = grid_from_rows(
            "#######",
            "#.....#",
            "#.###.#",
            "#.....#",
            "#######",
        )
        one_stamina_state = DummyState(
            grid=grid,
            start=(1, 1),
            door=(1, 5),
            items=(ItemPlacement(kind="stamina", position=(3, 1), value=8),),
            initial_stamina=3,
            locked_door=False,
        )
        two_stamina_state = DummyState(
            grid=grid,
            start=(1, 1),
            door=(1, 5),
            items=(
                ItemPlacement(kind="stamina", position=(3, 1), value=8),
                ItemPlacement(kind="stamina", position=(3, 5), value=8),
            ),
            initial_stamina=3,
            locked_door=False,
        )

        common_kwargs = dict(
            target_agent_difficulty=0.5,
            difficulty_weight=0.0,
            segment_target_weight=0.0,
            segment_balance_weight=0.0,
            dead_segment_weight=0.0,
            stamina_usage_weight=8.0,
            target_stamina_usage_rate=1.0,
            final_stamina_weight=0.0,
            spacing_weight=0.0,
            coverage_weight=0.0,
            branching_weight=0.0,
            agent_config=AgentDifficultyConfig(agents_per_segment=10, random_seed=4),
        )
        one_stamina_breakdown = stamina_agent_difficulty_energy_breakdown(
            state=one_stamina_state,
            **common_kwargs,
        )
        two_stamina_breakdown = stamina_agent_difficulty_energy_breakdown(
            state=two_stamina_state,
            **common_kwargs,
        )

        # initial_stamina=3 direkt plani oldurur: tek item'li haritada item
        # zorunludur (min_usage=1.0). Iki item'li haritada tek item toplayan
        # plan gecerli kalir (min_usage=0.5), bu yuzden hedef 1.0'a gore ceza
        # daha yuksektir.
        self.assertAlmostEqual(one_stamina_breakdown.stamina_usage_actual, 1.0)
        self.assertAlmostEqual(two_stamina_breakdown.stamina_usage_actual, 0.5)
        self.assertGreater(
            two_stamina_breakdown.stamina_usage_term,
            one_stamina_breakdown.stamina_usage_term,
        )


if __name__ == "__main__":
    unittest.main()
