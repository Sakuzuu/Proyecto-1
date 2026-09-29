"""Academic performance analysis logic for StudyFlow."""
from dataclasses import dataclass
import math
import os
from typing import Sequence

from calculations import average, weighted_average
from models import Evaluation, Exam, Subject


DEFAULT_STRENGTH_THRESHOLD = 90.0
DEFAULT_ATTENTION_THRESHOLD = 75.0


@dataclass(frozen=True)
class PerformanceThresholds:
    """Configurable boundaries for academic classification."""

    strength: float = DEFAULT_STRENGTH_THRESHOLD
    attention: float = DEFAULT_ATTENTION_THRESHOLD

    def __post_init__(self) -> None:
        for name, value in (("strength", self.strength), ("attention", self.attention)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} threshold must be a number.")
            if not math.isfinite(float(value)) or not 0 <= float(value) <= 100:
                raise ValueError(f"{name} threshold must be between 0 and 100.")
        if float(self.attention) >= float(self.strength):
            raise ValueError("attention threshold must be lower than strength threshold.")


def get_default_thresholds() -> PerformanceThresholds:
    """Read deployment defaults from environment variables, with safe fallbacks."""
    try:
        strength = float(os.getenv("STUDYFLOW_STRENGTH_THRESHOLD", DEFAULT_STRENGTH_THRESHOLD))
        attention = float(os.getenv("STUDYFLOW_ATTENTION_THRESHOLD", DEFAULT_ATTENTION_THRESHOLD))
        return PerformanceThresholds(strength, attention)
    except (TypeError, ValueError):
        return PerformanceThresholds()


def calculate_average(grades: Sequence[float]) -> float:
    """Backward-compatible name for the arithmetic mean."""
    return average(grades)


def calculate_weighted_average(grades: Sequence[float], weights: Sequence[float]) -> float:
    """Calculate a weighted average for academic results."""
    return weighted_average(grades, weights)


def _latest_evaluations_by_exam(evaluations: Sequence[Evaluation]) -> dict[int, Evaluation]:
    latest: dict[int, Evaluation] = {}
    for evaluation in evaluations:
        current = latest.get(evaluation.exam_id)
        if current is None or (evaluation.date, evaluation.id or 0) > (
            current.date,
            current.id or 0,
        ):
            latest[evaluation.exam_id] = evaluation
    return latest


def build_average_report(
    subjects: Sequence[Subject],
    exams: Sequence[Exam],
    evaluations: Sequence[Evaluation],
) -> dict:
    """Build current averages using the most recent result for each exam.

    Historical evaluations remain stored, but only the latest evaluation of
    each exam contributes to the current academic average. Exam weights are
    used for weighted averages; when all relevant weights are zero, the
    arithmetic average is used instead.
    """
    latest = _latest_evaluations_by_exam(evaluations)
    subject_rows = []
    all_grades: list[float] = []
    all_weights: list[float] = []

    for subject in sorted(subjects, key=lambda item: item.name.casefold()):
        grades: list[float] = []
        weights: list[float] = []

        for exam in exams:
            if exam.subject_id != subject.id:
                continue
            evaluation = latest.get(exam.id)
            if evaluation is None:
                continue
            grades.append(evaluation.grade)
            weights.append(exam.weight)
            all_grades.append(evaluation.grade)
            all_weights.append(exam.weight)

        simple_average = calculate_average(grades)
        if grades and sum(weights) > 0:
            current_average = calculate_weighted_average(grades, weights)
        else:
            current_average = simple_average

        subject_rows.append(
            {
                "subject_id": subject.id,
                "subject_name": subject.name,
                "target_grade": subject.target_grade,
                "average": round(current_average, 2),
                "simple_average": round(simple_average, 2),
                "evaluation_count": len(grades),
            }
        )

    if all_grades and sum(all_weights) > 0:
        general_average = calculate_weighted_average(all_grades, all_weights)
    else:
        general_average = calculate_average(all_grades)

    return {
        "general_average": round(general_average, 2),
        "evaluated_exams": len(latest),
        "total_evaluations": len(evaluations),
        "subjects": subject_rows,
    }


def _trend_stats(grades: Sequence[float]) -> tuple[str, float | None, str]:
    """Return trend direction, relative percentage and display label."""
    if len(grades) < 2:
        return "insufficient", None, "→ Sin datos suficientes"
    midpoint = len(grades) // 2
    previous_average = calculate_average(grades[:midpoint])
    recent_average = calculate_average(grades[midpoint:])
    if previous_average == 0:
        if recent_average == 0:
            return "flat", 0.0, "→ 0.0%"
        return "up", None, "↑ N/D"
    change = ((recent_average - previous_average) / previous_average) * 100
    if abs(change) < 0.05:
        return "flat", round(change, 2), "→ 0.0%"
    direction = "up" if change > 0 else "down"
    arrow = "↑" if change > 0 else "↓"
    return direction, round(change, 2), f"{arrow} {change:+.1f}%"


def detect_trend(grades: Sequence[float]) -> str:
    """Describe the change between earlier and more recent results."""
    return _trend_stats(grades)[2]


def build_performance_report(
    subjects: Sequence[Subject],
    exams: Sequence[Exam],
    evaluations: Sequence[Evaluation],
) -> dict:
    """Build the dashboard metrics for academic performance."""
    average_report = build_average_report(subjects, exams, evaluations)
    exam_to_subject = {exam.id: exam.subject_id for exam in exams}
    subject_rows = []
    for row in average_report["subjects"]:
        history = sorted(
            (
                evaluation
                for evaluation in evaluations
                if exam_to_subject.get(evaluation.exam_id) == row["subject_id"]
            ),
            key=lambda evaluation: (evaluation.date, evaluation.id or 0),
        )
        direction, change, label = _trend_stats(
            [evaluation.grade for evaluation in history]
        )
        subject_rows.append(
            {
                **row,
                "trend": label,
                "trend_status": direction,
                "trend_change_percent": change,
            }
        )

    evaluated = [row for row in subject_rows if row["evaluation_count"] > 0]
    ordered_desc = sorted(
        evaluated, key=lambda row: (-row["average"], row["subject_name"].casefold())
    )
    ordered_asc = sorted(
        evaluated, key=lambda row: (row["average"], row["subject_name"].casefold())
    )
    best = ordered_desc[0] if ordered_desc else None
    lowest = ordered_asc[0] if ordered_asc else None

    all_history = sorted(
        evaluations, key=lambda evaluation: (evaluation.date, evaluation.id or 0)
    )
    overall_direction, overall_change, overall_label = _trend_stats(
        [evaluation.grade for evaluation in all_history]
    )
    return {
        "general_average": average_report["general_average"],
        "evaluated_exams": average_report["evaluated_exams"],
        "total_evaluations": average_report["total_evaluations"],
        "evaluated_subjects": len(evaluated),
        "best_subject": best,
        "lowest_subject": lowest,
        "overall_trend": overall_label,
        "overall_trend_status": overall_direction,
        "overall_trend_change_percent": overall_change,
        "subjects": subject_rows,
    }


def _classify_average(average_grade: float, thresholds: PerformanceThresholds) -> str:
    if average_grade >= thresholds.strength:
        return "strength"
    if average_grade < thresholds.attention:
        return "attention"
    return "normal"


def _classification_label(classification: str) -> str:
    return {
        "strength": "Fortaleza",
        "normal": "Normal",
        "attention": "Atención",
        "no_data": "Sin datos",
    }[classification]


def detect_strengths_and_weaknesses(
    subjects: Sequence[Subject],
    exams: Sequence[Exam],
    evaluations: Sequence[Evaluation],
    strength_threshold: float | None = None,
    attention_threshold: float | None = None,
) -> dict:
    """Transform academic averages and trends into actionable classifications.

    A subject is a strength when its current average is at or above the
    strength threshold, normal when it is between the thresholds, and
    attention when it is below the attention threshold. Thresholds are
    configurable and validated before any classification is produced.
    """
    defaults = get_default_thresholds()
    thresholds = PerformanceThresholds(
        defaults.strength if strength_threshold is None else float(strength_threshold),
        defaults.attention if attention_threshold is None else float(attention_threshold),
    )
    performance = build_performance_report(subjects, exams, evaluations)

    enriched_rows = []
    strengths = []
    normal = []
    attention = []
    without_data = []
    trends = []

    for row in performance["subjects"]:
        if row["evaluation_count"] == 0:
            classification = "no_data"
        else:
            classification = _classify_average(row["average"], thresholds)

        enriched = {
            **row,
            "classification": classification,
            "classification_label": _classification_label(classification),
        }
        enriched_rows.append(enriched)

        if classification == "strength":
            strengths.append(enriched)
        elif classification == "normal":
            normal.append(enriched)
        elif classification == "attention":
            attention.append(enriched)
        else:
            without_data.append(enriched)

        if row["evaluation_count"] > 0:
            trends.append(
                {
                    "subject_id": row["subject_id"],
                    "subject_name": row["subject_name"],
                    "trend": row["trend"],
                    "trend_status": row["trend_status"],
                    "trend_change_percent": row["trend_change_percent"],
                }
            )

    return {
        "thresholds": {
            "strength": thresholds.strength,
            "attention": thresholds.attention,
        },
        "strengths": strengths,
        "normal": normal,
        "attention": attention,
        "without_data": without_data,
        "trends": trends,
        "subjects": enriched_rows,
    }


def build_strength_weakness_report(
    subjects: Sequence[Subject],
    exams: Sequence[Exam],
    evaluations: Sequence[Evaluation],
    strength_threshold: float | None = None,
    attention_threshold: float | None = None,
) -> dict:
    """Named alias for the milestone-11 analysis API."""
    return detect_strengths_and_weaknesses(
        subjects,
        exams,
        evaluations,
        strength_threshold,
        attention_threshold,
    )
