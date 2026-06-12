from __future__ import annotations

import random
import unittest

from utils.agent_difficulty import (
    AgentDifficultyConfig,
    enumerate_semantic_solution_plans,
    estimate_agent_difficulty,
    simulate_segment_agent,
)
from utils.hard_constraints import StaminaOnlyHC3Problem
from utils.map_entities import ItemPlacement


def grid_from_rows(*rows: str) -> list[list[int]]:
    return [[0 if cell == "." else 1 for cell in row] for row in rows]


class AgentDifficultyTests(unittest.TestCase):
    def test_agent_follows_visible_path_to_target(self) -> None:
        result = simulate_segment_agent(
            grid=grid_from_rows(
                "#####",
                "#...#",
                "#.###",
                "#####",
            ),
            source=(1, 1),
            target=(1, 3),
            blocked_positions=set(),
            start_stamina=2,
            rng=random.Random(0),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.total_steps, 2)
        self.assertEqual(result.remaining_stamina, 0)

    def test_enumerates_multiple_semantic_solution_plans(self) -> None:
        problem = StaminaOnlyHC3Problem(
            grid=grid_from_rows(
                "#######",
                "#.....#",
                "#.###.#",
                "#.....#",
                "#######",
            ),
            start=(1, 1),
            door=(1, 5),
            items=(
                ItemPlacement(kind="stamina", position=(3, 1), value=4),
            ),
            initial_stamina=10,
            locked_door=False,
        )

        plans = enumerate_semantic_solution_plans(problem)
        plan_kinds = {tuple(step.kind for step in plan.steps) for plan in plans}

        self.assertIn(("start", "door"), plan_kinds)
        self.assertIn(("start", "item:stamina", "door"), plan_kinds)

    def test_stamina_item_effect_is_propagated_to_next_segment(self) -> None:
        problem = StaminaOnlyHC3Problem(
            grid=grid_from_rows(
                "#########",
                "#.......#",
                "#########",
            ),
            start=(1, 1),
            door=(1, 7),
            items=(ItemPlacement(kind="stamina", position=(1, 3), value=4),),
            initial_stamina=3,
            locked_door=False,
        )

        summary = estimate_agent_difficulty(
            problem,
            config=AgentDifficultyConfig(agents_per_segment=10, random_seed=1),
        )
        best_plan = max(
            summary.plan_summaries,
            key=lambda plan_summary: plan_summary.estimated_success_rate,
        )

        self.assertEqual(
            tuple(step.kind for step in best_plan.plan.steps),
            ("start", "item:stamina", "door"),
        )
        self.assertTrue(best_plan.final_stamina_samples)
        self.assertTrue(all(stamina >= 0 for stamina in best_plan.final_stamina_samples))

    def test_exact_dead_plan_contributes_dead_segment_not_main_route(self) -> None:
        problem = StaminaOnlyHC3Problem(
            grid=grid_from_rows(
                "#######",
                "#.....#",
                "#.###.#",
                "#.....#",
                "#######",
            ),
            start=(1, 1),
            door=(1, 5),
            items=(ItemPlacement(kind="stamina", position=(3, 1), value=0),),
            initial_stamina=4,
            locked_door=False,
        )

        plans = enumerate_semantic_solution_plans(problem)
        plan_by_kinds = {
            tuple(step.kind for step in plan.steps): plan
            for plan in plans
        }

        self.assertTrue(plan_by_kinds[("start", "door")].semantic_success)
        self.assertFalse(plan_by_kinds[("start", "item:stamina", "door")].semantic_success)

        summary = estimate_agent_difficulty(
            problem,
            config=AgentDifficultyConfig(agents_per_segment=10, random_seed=5),
        )

        self.assertEqual(summary.average_plan_success_rate, summary.main_route_success_rate)
        self.assertEqual(summary.best_plan_success_rate, summary.main_route_success_rate)
        self.assertGreater(summary.dead_segment_ratio, 0.0)
        self.assertGreater(summary.dead_segment_count, 0)

    def test_locked_inactive_door_is_not_enumerated_as_target_before_key(self) -> None:
        problem = StaminaOnlyHC3Problem(
            grid=grid_from_rows(
                "########",
                "#......#",
                "########",
            ),
            start=(1, 1),
            door=(1, 3),
            items=(ItemPlacement(kind="key", position=(1, 6), value=0),),
            initial_stamina=10,
            locked_door=True,
        )

        plans = enumerate_semantic_solution_plans(problem)
        plan_kinds = {tuple(step.kind for step in plan.steps) for plan in plans}

        self.assertNotIn(("start", "door"), plan_kinds)
        self.assertIn(("start", "item:key", "door"), plan_kinds)

    def test_locked_inactive_door_is_transit_inside_agent_segment(self) -> None:
        problem = StaminaOnlyHC3Problem(
            grid=grid_from_rows(
                "########",
                "#......#",
                "########",
            ),
            start=(1, 1),
            door=(1, 3),
            items=(ItemPlacement(kind="key", position=(1, 6), value=0),),
            initial_stamina=10,
            locked_door=True,
        )

        summary = estimate_agent_difficulty(
            problem,
            config=AgentDifficultyConfig(agents_per_segment=10, random_seed=7),
        )
        key_plan = next(
            plan_summary
            for plan_summary in summary.plan_summaries
            if tuple(step.kind for step in plan_summary.plan.steps) == ("start", "item:key", "door")
        )

        self.assertEqual(key_plan.segment_summaries[0].success_rate, 1.0)

    def test_collected_item_is_transit_for_later_semantic_segments(self) -> None:
        problem = StaminaOnlyHC3Problem(
            grid=grid_from_rows(
                "########",
                "#......#",
                "########",
            ),
            start=(1, 1),
            door=(1, 2),
            items=(
                ItemPlacement(kind="key", position=(1, 4), value=0),
                ItemPlacement(kind="stamina", position=(1, 6), value=0),
            ),
            initial_stamina=20,
            locked_door=True,
        )

        plans = enumerate_semantic_solution_plans(problem)
        plan_kinds = {tuple(step.kind for step in plan.steps) for plan in plans}

        self.assertIn(("start", "item:key", "item:stamina", "door"), plan_kinds)

    def test_zero_agent_success_does_not_create_dead_segment(self) -> None:
        problem = StaminaOnlyHC3Problem(
            grid=grid_from_rows(
                "########",
                "#......#",
                "########",
            ),
            start=(1, 1),
            door=(1, 3),
            items=(ItemPlacement(kind="key", position=(1, 6), value=0),),
            initial_stamina=10,
            locked_door=True,
        )

        summary = estimate_agent_difficulty(
            problem,
            config=AgentDifficultyConfig(agents_per_segment=0, random_seed=8),
        )

        self.assertEqual(summary.dead_segment_count, 0)
        self.assertEqual(summary.unique_segment_count, 1)
        self.assertEqual(summary.dead_segment_ratio, 0.0)

    def test_zero_agent_success_on_exact_segment_is_not_dead_segment(self) -> None:
        problem = StaminaOnlyHC3Problem(
            grid=grid_from_rows(
                "#######",
                "#.....#",
                "#######",
            ),
            start=(1, 1),
            door=(1, 5),
            initial_stamina=10,
            locked_door=False,
        )

        summary = estimate_agent_difficulty(
            problem,
            config=AgentDifficultyConfig(agents_per_segment=0, random_seed=9),
        )

        self.assertEqual(summary.dead_segment_count, 0)
        self.assertEqual(summary.unique_segment_count, 1)
        self.assertEqual(summary.dead_segment_ratio, 0.0)

    def test_semantic_plan_enumeration_deduplicates_same_scored_prefix(self) -> None:
        problem = StaminaOnlyHC3Problem(
            grid=grid_from_rows(
                "#######",
                "#.....#",
                "#.....#",
                "#.....#",
                "#######",
            ),
            start=(1, 1),
            door=(3, 5),
            items=(
                ItemPlacement(kind="stamina", position=(3, 1), value=0),
                ItemPlacement(kind="stamina", position=(1, 5), value=0),
            ),
            initial_stamina=1,
            locked_door=False,
        )

        plans = enumerate_semantic_solution_plans(problem)
        plan_keys = [(plan.node_ids, plan.semantic_success) for plan in plans]

        self.assertEqual(len(plan_keys), len(set(plan_keys)))

    def test_agent_difficulty_is_deterministic_for_same_problem_and_config(self) -> None:
        problem = StaminaOnlyHC3Problem(
            grid=grid_from_rows(
                "#######",
                "#.....#",
                "#.###.#",
                "#.....#",
                "#######",
            ),
            start=(1, 1),
            door=(3, 5),
            items=(ItemPlacement(kind="stamina", position=(3, 1), value=3),),
            initial_stamina=10,
            locked_door=False,
        )
        config = AgentDifficultyConfig(agents_per_segment=20, random_seed=99)

        first = estimate_agent_difficulty(problem, config=config)
        second = estimate_agent_difficulty(problem, config=config)

        self.assertEqual(first.difficulty_score, second.difficulty_score)
        self.assertEqual(first.best_plan_success_rate, second.best_plan_success_rate)


if __name__ == "__main__":
    unittest.main()
