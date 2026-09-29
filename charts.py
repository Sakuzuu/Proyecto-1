"""Matplotlib chart utilities for StudyFlow."""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

import analyzer
from models import Evaluation, Exam, Subject, Task


def _empty_figure(title: str, message: str):
    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.set_title(title)
    axis.text(0.5, 0.5, message, ha="center", va="center", transform=axis.transAxes)
    axis.set_axis_off()
    figure.tight_layout()
    return figure


def _finalize(figure, axis):
    axis.grid(axis="y", alpha=0.2)
    figure.tight_layout()
    return figure


def plot_grade_evolution(
    evaluations: Sequence[Evaluation],
    exams: Sequence[Exam],
    subjects: Sequence[Subject],
):
    """Return a line chart of historical grades grouped by subject and date."""
    exam_to_subject = {exam.id: exam.subject_id for exam in exams}
    subject_names = {subject.id: subject.name for subject in subjects}
    grouped = defaultdict(lambda: defaultdict(list))

    for evaluation in evaluations:
        subject_id = exam_to_subject.get(evaluation.exam_id)
        if subject_id is None or subject_id not in subject_names:
            continue
        grouped[subject_names[subject_id]][evaluation.date].append(evaluation.grade)

    if not grouped:
        return _empty_figure("Evolución de notas", "Aún no hay evaluaciones registradas.")

    figure, axis = plt.subplots(figsize=(9, 4.8))
    for subject_name in sorted(grouped, key=str.casefold):
        dates = sorted(grouped[subject_name])
        grades = [
            sum(grouped[subject_name][day]) / len(grouped[subject_name][day])
            for day in dates
        ]
        axis.plot(dates, grades, marker="o", linewidth=2, label=subject_name)

    axis.set_title("Evolución de notas")
    axis.set_xlabel("Fecha")
    axis.set_ylabel("Nota")
    axis.set_ylim(0, 100)
    axis.legend(loc="best")
    figure.autofmt_xdate()
    return _finalize(figure, axis)


def plot_subject_averages(
    subjects: Sequence[Subject],
    exams: Sequence[Exam],
    evaluations: Sequence[Evaluation],
):
    """Return a horizontal bar chart with each subject's current average."""
    report = analyzer.build_average_report(subjects, exams, evaluations)
    evaluated = [row for row in report["subjects"] if row["evaluation_count"] > 0]

    if not evaluated:
        return _empty_figure("Promedio por materia", "Aún no hay materias con evaluaciones.")

    ordered = sorted(evaluated, key=lambda row: row["average"])
    names = [row["subject_name"] for row in ordered]
    averages = [row["average"] for row in ordered]

    figure, axis = plt.subplots(figsize=(9, max(4.5, len(names) * 0.55)))
    axis.barh(names, averages)
    axis.set_title("Promedio por materia")
    axis.set_xlabel("Promedio")
    axis.set_xlim(0, 100)

    for index, value in enumerate(averages):
        axis.text(min(value + 1, 97), index, f"{value:.1f}", va="center")

    return _finalize(figure, axis)


def plot_study_time(
    tasks: Sequence[Task],
    subjects: Sequence[Subject],
):
    """Return estimated study time by subject, based on task durations."""
    subject_names = {subject.id: subject.name for subject in subjects}
    totals = defaultdict(int)
    for task in tasks:
        subject_name = subject_names.get(task.subject_id)
        if subject_name is not None:
            totals[subject_name] += task.estimated_minutes

    if not totals:
        return _empty_figure(
            "Tiempo de estudio estimado",
            "Aún no hay tareas con tiempo estimado.",
        )

    ordered = sorted(totals.items(), key=lambda item: item[1])
    names = [name for name, _ in ordered]
    hours = [minutes / 60 for _, minutes in ordered]

    figure, axis = plt.subplots(figsize=(9, max(4.5, len(names) * 0.55)))
    axis.barh(names, hours)
    axis.set_title("Tiempo de estudio estimado por materia")
    axis.set_xlabel("Horas")
    return _finalize(figure, axis)


def close_figure(figure) -> None:
    """Release matplotlib resources after a figure is rendered."""
    plt.close(figure)
