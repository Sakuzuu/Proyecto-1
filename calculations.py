"""Reusable mathematical calculations."""
from typing import Sequence

def weighted_average(values: Sequence[float], weights: Sequence[float]) -> float:
    if len(values) != len(weights):
        raise ValueError("Values and weights must have the same length.")
    if not values:
        return 0.0
    total_weight = sum(weights)
    if total_weight <= 0:
        raise ValueError("The total weight must be greater than zero.")
    return sum(v * w for v, w in zip(values, weights)) / total_weight
