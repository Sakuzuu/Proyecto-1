"""Reusable mathematical calculations for StudyFlow."""
import math
from typing import Sequence


def _validate_number(value: float, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a finite number.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a finite number.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be a finite number.")
    return number


def average(values: Sequence[float]) -> float:
    """Return the arithmetic mean, or 0.0 for an empty sequence."""
    if not values:
        return 0.0
    numbers = [_validate_number(value, "value") for value in values]
    return sum(numbers) / len(numbers)


def weighted_average(values: Sequence[float], weights: Sequence[float]) -> float:
    """Return a weighted mean using non-negative weights."""
    if len(values) != len(weights):
        raise ValueError("Values and weights must have the same length.")
    if not values:
        return 0.0

    numbers = [_validate_number(value, "value") for value in values]
    validated_weights = []
    for weight in weights:
        number = _validate_number(weight, "weight")
        if number < 0:
            raise ValueError("Weights must be non-negative.")
        validated_weights.append(number)

    total_weight = sum(validated_weights)
    if total_weight <= 0:
        raise ValueError("The total weight must be greater than zero.")
    return sum(value * weight for value, weight in zip(numbers, validated_weights)) / total_weight
