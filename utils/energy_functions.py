from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Protocol

from utils.hard_constraints import (
    StaminaOnlyHC3GraphCache,
    StaminaOnlyHC3Problem,
    StaminaOnlySolutionStep,
    analyze_stamina_only_hc3,
)
from utils.map_analysis import shortest_path_length


class EnergyState(Protocol):
    grid: list[list[int]]
    start: tuple[int, int]
    door: tuple[int, int]


class StaminaAwareEnergyState(EnergyState, Protocol):
    items: tuple[object, ...]
    initial_stamina: int
    locked_door: bool


STAMINA_ENERGY_CACHE = StaminaOnlyHC3GraphCache()


@dataclass(frozen=True)
class EnergyBreakdown:
    mode: str
    total_energy: float
    path_target: int | None = None
    path_actual: int | None = None
    path_term: float | None = None
    remaining_stamina_target: int | None = None
    remaining_stamina_actual: int | None = None
    remaining_stamina_term: float | None = None
    solution_steps: tuple[StaminaOnlySolutionStep, ...] = ()


def path_length_target_energy(state: EnergyState, target_path_length: int) -> float:
    path_length = shortest_path_length(state.grid, state.start, state.door)

    if path_length is None:
        return math.inf

    return abs(path_length - target_path_length)


def make_path_length_energy(target_path_length: int) -> Callable[[EnergyState], float]:
    def energy_function(state: EnergyState) -> float:
        return path_length_target_energy(state, target_path_length)

    return energy_function


def stamina_aware_baseline_energy(
    state: StaminaAwareEnergyState,
    target_path_length: int,
    target_remaining_stamina: int = 0,
    path_weight: float = 1.0,
    stamina_weight: float = 1.0,
) -> float:
    analysis = analyze_stamina_only_hc3(
        problem=StaminaOnlyHC3Problem(
            grid=state.grid,
            start=state.start,
            door=state.door,
            items=state.items,
            initial_stamina=state.initial_stamina,
            locked_door=state.locked_door,
        ),
        cache=STAMINA_ENERGY_CACHE,
    )

    if (
        not analysis.solvable
        or analysis.shortest_success_path_length is None
        or analysis.best_remaining_stamina is None
    ):
        return math.inf

    path_term = abs(analysis.shortest_success_path_length - target_path_length)
    stamina_term = abs(analysis.best_remaining_stamina - target_remaining_stamina)
    return (path_weight * path_term) + (stamina_weight * stamina_term)


def stamina_aware_baseline_energy_breakdown(
    state: StaminaAwareEnergyState,
    target_path_length: int,
    target_remaining_stamina: int = 0,
    path_weight: float = 1.0,
    stamina_weight: float = 1.0,
) -> EnergyBreakdown:
    analysis = analyze_stamina_only_hc3(
        problem=StaminaOnlyHC3Problem(
            grid=state.grid,
            start=state.start,
            door=state.door,
            items=state.items,
            initial_stamina=state.initial_stamina,
            locked_door=state.locked_door,
        ),
        cache=STAMINA_ENERGY_CACHE,
    )

    if (
        not analysis.solvable
        or analysis.shortest_success_path_length is None
        or analysis.best_remaining_stamina is None
    ):
        return EnergyBreakdown(mode="stamina_only", total_energy=math.inf)

    path_term = path_weight * abs(analysis.shortest_success_path_length - target_path_length)
    stamina_term = stamina_weight * abs(analysis.best_remaining_stamina - target_remaining_stamina)
    return EnergyBreakdown(
        mode="stamina_only",
        total_energy=path_term + stamina_term,
        path_target=target_path_length,
        path_actual=analysis.shortest_success_path_length,
        path_term=path_term,
        remaining_stamina_target=target_remaining_stamina,
        remaining_stamina_actual=analysis.best_remaining_stamina,
        remaining_stamina_term=stamina_term,
        solution_steps=analysis.solution_steps,
    )


def make_stamina_aware_baseline_energy(
    target_path_length: int,
    target_remaining_stamina: int = 0,
    path_weight: float = 1.0,
    stamina_weight: float = 1.0,
) -> Callable[[StaminaAwareEnergyState], float]:
    def energy_function(state: StaminaAwareEnergyState) -> float:
        return stamina_aware_baseline_energy(
            state=state,
            target_path_length=target_path_length,
            target_remaining_stamina=target_remaining_stamina,
            path_weight=path_weight,
            stamina_weight=stamina_weight,
        )

    return energy_function


def path_length_energy_breakdown(
    state: EnergyState,
    target_path_length: int,
) -> EnergyBreakdown:
    path_length = shortest_path_length(state.grid, state.start, state.door)

    if path_length is None:
        return EnergyBreakdown(mode="door_only", total_energy=math.inf)

    path_term = abs(path_length - target_path_length)
    return EnergyBreakdown(
        mode="door_only",
        total_energy=path_term,
        path_target=target_path_length,
        path_actual=path_length,
        path_term=path_term,
    )
