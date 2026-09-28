"""Core StudyFlow data models."""
from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class Subject:
    id: Optional[int]
    name: str
    professor: str = ""
    target_grade: float = 0.0

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
