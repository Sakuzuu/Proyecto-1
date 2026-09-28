"""Core StudyFlow data models and validation."""
from dataclasses import dataclass
from datetime import date
import math
from typing import Optional


class ModelValidationError(ValueError):
    """Raised when a model contains invalid data."""


def _clean_required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ModelValidationError(f"{field_name} must be a string.")
    value = value.strip()
    if not value:
        raise ModelValidationError(f"{field_name} cannot be empty.")
    return value


def _clean_optional_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ModelValidationError(f"{field_name} must be a string.")
    return value.strip()


def _clean_id(value: Optional[int], field_name: str = "id") -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ModelValidationError(f"{field_name} must be a positive integer or None.")
    return value


def _clean_target_grade(value: float) -> float:
    if isinstance(value, bool):
        raise ModelValidationError("target_grade must be a number between 0 and 100.")
    try:
        grade = float(value)
    except (TypeError, ValueError) as exc:
        raise ModelValidationError(
            "target_grade must be a number between 0 and 100."
        ) from exc
    if not math.isfinite(grade) or not 0 <= grade <= 100:
        raise ModelValidationError("target_grade must be between 0 and 100.")
    return grade


@dataclass
class Subject:
    """Academic subject stored by StudyFlow."""

    id: Optional[int]
    name: str
    professor: str = ""
    target_grade: float = 0.0

    def __post_init__(self) -> None:
        self.id = _clean_id(self.id)
        self.name = _clean_required_text(self.name, "name")
        self.professor = _clean_optional_text(self.professor, "professor")
        self.target_grade = _clean_target_grade(self.target_grade)


@dataclass
class Task:
    id: Optional[int]
    subject_id: int
    name: str
    description: str
    deadline: date
    difficulty: int
    estimated_minutes: int
    progress: int = 0
    status: str = "pending"


@dataclass
class Exam:
    id: Optional[int]
    subject_id: int
    name: str
    date: date
    difficulty: int
    weight: float


@dataclass
class Evaluation:
    id: Optional[int]
    exam_id: int
    grade: float
    date: date
    evaluation_type: str
