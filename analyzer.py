"""Academic performance analysis logic for StudyFlow."""
from typing import Sequence

from calculations import average, weighted_average
from models import Evaluation, Exam, Subject


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


def detect_strengths_and_weaknesses(*args, **kwargs):
    raise NotImplementedError("Strength/weakness analysis belongs to milestone 11.")
