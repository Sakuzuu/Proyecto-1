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


def detect_trend(grades: Sequence[float]) -> str:
    raise NotImplementedError("Trend detection belongs to milestone 9.")


def detect_strengths_and_weaknesses(*args, **kwargs):
    raise NotImplementedError("Strength/weakness analysis belongs to milestone 11.")
