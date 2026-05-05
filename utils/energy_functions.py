from __future__ import annotations

import math
from typing import Callable, Protocol

from utils.map_analysis import shortest_path_length


class EnergyState(Protocol):
    grid: list[list[int]]
    start: tuple[int, int]
    door: tuple[int, int]


def path_length_target_energy(state: EnergyState, target_path_length: int) -> float:
    path_length = shortest_path_length(state.grid, state.start, state.door)

    if path_length is None:
        return math.inf

    return abs(path_length - target_path_length)


def make_path_length_energy(target_path_length: int) -> Callable[[EnergyState], float]:
    def energy_function(state: EnergyState) -> float:
        return path_length_target_energy(state, target_path_length)

    return energy_function
