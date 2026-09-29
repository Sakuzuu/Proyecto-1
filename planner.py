"""Priority calculation and daily study-plan generation for StudyFlow."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import math
from typing import Any, Iterable, Mapping, Optional


@dataclass(frozen=True)
class PlanSession:
    kind: str
    source_id: int
    subject_id: int
    subject_name: str
    title: str
    minutes: int
    priority: float
    deadline: date
    start: datetime
    end: datetime

    @property
    def purpose(self) -> str:
        return "Preparación para examen" if self.kind == "exam" else "Tarea pendiente"


def _get(item: Any, key: str, default: Any = None) -> Any:
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def _date(item: Any, kind: str) -> date:
    value = _get(item, "deadline" if kind == "task" else "date")
    if not isinstance(value, date):
        raise ValueError(f"{kind} date must be a datetime.date instance.")
    return value


def _clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return max(low, min(high, value))


def calculate_priority(item: Any, today: Optional[date] = None) -> float:
    """Return a 0–10 priority using urgency, difficulty and remaining work."""
    today = today or date.today()
    kind = "task" if _get(item, "deadline") is not None else "exam"
    deadline = _date(item, kind)
    days = (deadline - today).days
    urgency = 10.0 if days <= 0 else _clamp(10.0 - 1.5 * days, 1.0, 10.0)
    difficulty = _clamp(float(_get(item, "difficulty", 1)), 1.0, 10.0)

    if kind == "task":
        progress = float(_get(item, "progress", 0))
        if _get(item, "status") == "completed" or progress >= 100:
            return 0.0
        remaining = _clamp((100.0 - progress) / 10.0)
        score = 0.50 * urgency + 0.25 * difficulty + 0.25 * remaining
    else:
        weight = _clamp(float(_get(item, "weight", 0)) / 10.0)
        score = 0.50 * urgency + 0.30 * difficulty + 0.20 * weight
    return round(_clamp(score), 2)


def estimate_exam_minutes(exam: Any) -> int:
    """Estimate one preparation block from exam difficulty and weight."""
    difficulty = float(_get(exam, "difficulty", 5))
    weight = float(_get(exam, "weight", 0))
    return int(_clamp(round(25 + 8 * difficulty + 0.25 * weight), 45, 120))


def _remaining_task_minutes(task: Any) -> int:
    estimated = int(_get(task, "estimated_minutes", 0))
    progress = float(_get(task, "progress", 0))
    return max(0, math.ceil(estimated * (100 - progress) / 100))


def rank_study_items(tasks: Iterable[Any], exams: Iterable[Any], today: Optional[date] = None) -> list[dict[str, Any]]:
    """Return tasks/exams ranked by priority, with overdue items marked."""
    today = today or date.today()
    items: list[dict[str, Any]] = []
    for task in tasks:
        if _get(task, "status", "pending") == "completed" or float(_get(task, "progress", 0)) >= 100:
            continue
        deadline = _date(task, "task")
        items.append({
            "kind": "task", "id": int(_get(task, "id", 0)), "subject_id": int(_get(task, "subject_id")),
            "title": str(_get(task, "name", "Tarea")), "deadline": deadline,
            "priority": calculate_priority(task, today), "remaining_minutes": _remaining_task_minutes(task),
            "overdue": deadline < today,
        })
    for exam in exams:
        deadline = _date(exam, "exam")
        items.append({
            "kind": "exam", "id": int(_get(exam, "id", 0)), "subject_id": int(_get(exam, "subject_id")),
            "title": str(_get(exam, "name", "Examen")), "deadline": deadline,
            "priority": calculate_priority(exam, today), "remaining_minutes": estimate_exam_minutes(exam),
            "overdue": deadline < today,
        })
    items.sort(key=lambda x: (-x["priority"], x["deadline"], x["kind"], x["id"]))
    return items


def _round_up_to_five_minutes(value: datetime) -> datetime:
    minute = ((value.minute + 4) // 5) * 5
    if minute >= 60:
        value += timedelta(hours=1)
        minute = 0
    return value.replace(minute=minute, second=0, microsecond=0)


def generate_study_plan(
    tasks: Iterable[Any],
    exams: Iterable[Any],
    available_hours: float,
    start_datetime: Optional[datetime] = None,
    break_minutes: int = 15,
    max_session_minutes: int = 80,
    today: Optional[date] = None,
    subject_names: Optional[Mapping[int, str]] = None,
) -> list[PlanSession]:
    """Allocate study time without exceeding the budget or any date constraint."""
    if isinstance(available_hours, bool):
        raise ValueError("available_hours must be a positive number.")
    try:
        hours = float(available_hours)
    except (TypeError, ValueError) as exc:
        raise ValueError("available_hours must be a positive number.") from exc
    if not math.isfinite(hours) or hours <= 0:
        raise ValueError("available_hours must be greater than 0.")
    if isinstance(break_minutes, bool) or not isinstance(break_minutes, int) or break_minutes < 0:
        raise ValueError("break_minutes must be a non-negative integer.")
    if isinstance(max_session_minutes, bool) or not isinstance(max_session_minutes, int) or max_session_minutes <= 0:
        raise ValueError("max_session_minutes must be a positive integer.")

    start = _round_up_to_five_minutes(start_datetime or datetime.now())
    today = today or start.date()
    if start.date() != today:
        return []
    budget = int(math.floor(hours * 60 + 1e-9))
    if budget <= 0:
        raise ValueError("available_hours must represent at least one minute.")

    task_list, exam_list = list(tasks), list(exams)
    names = dict(subject_names or {})
    for item in task_list + exam_list:
        subject_id = int(_get(item, "subject_id"))
        names.setdefault(subject_id, str(_get(item, "subject_name", "Materia")))

    ranked = rank_study_items(task_list, exam_list, today)
    candidates = sorted(
        (item for item in ranked if not item["overdue"] and item["remaining_minutes"] > 0),
        key=lambda x: (x["deadline"], -x["priority"], x["kind"], x["id"]),
    )

    plan: list[PlanSession] = []
    cursor = start
    for item in candidates:
        remaining = item["remaining_minutes"]
        while remaining > 0 and budget > 0 and cursor.date() == today:
            minutes = min(remaining, budget, max_session_minutes)
            if item["deadline"] == today:
                day_end = datetime.combine(today, time.max).replace(microsecond=0)
                minutes = min(minutes, max(0, int((day_end - cursor).total_seconds() // 60)))
            if minutes <= 0:
                break
            end = cursor + timedelta(minutes=minutes)
            if end.date() != today or end.date() > item["deadline"]:
                break
            subject_name = names.get(item["subject_id"], "Materia")
            title = item["title"] if item["kind"] == "task" else f"Preparación: {item['title']}"
            plan.append(PlanSession(item["kind"], item["id"], item["subject_id"], subject_name, title, minutes, item["priority"], item["deadline"], cursor, end))
            remaining -= minutes
            budget -= minutes
            cursor = end + timedelta(minutes=break_minutes) if budget > 0 else end
            if item["kind"] == "exam":
                break
    return plan
