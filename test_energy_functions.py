from __future__ import annotations

from dataclasses import dataclass
import unittest

from utils.agent_difficulty import AgentDifficultyConfig
from utils.energy_functions import stamina_agent_difficulty_energy_breakdown


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
            target_agent_difficulty=0.5,
            difficulty_weight=0.0,
            segment_balance_weight=0.0,
            dead_segment_weight=0.0,
            final_stamina_weight=10.0,
            final_stamina_target_factor=0.8,
            agent_config=AgentDifficultyConfig(agents_per_segment=10, random_seed=1),
        )

        self.assertEqual(breakdown.remaining_stamina_target, 4.0)
        self.assertEqual(breakdown.remaining_stamina_actual, 6.0)
        self.assertAlmostEqual(breakdown.remaining_stamina_score, 0.2)
        self.assertAlmostEqual(breakdown.remaining_stamina_term, 2.0)
        self.assertAlmostEqual(breakdown.total_energy, 2.0)


if __name__ == "__main__":
    unittest.main()
