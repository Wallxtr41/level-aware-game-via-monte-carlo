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


if __name__ == "__main__":
    unittest.main()
