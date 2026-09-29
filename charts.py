"""Dependency-free SVG chart utilities for StudyFlow."""

from __future__ import annotations

from collections import defaultdict
from html import escape
from typing import Sequence


_PALETTE = (
    "#2563eb",
    "#16a34a",
    "#dc2626",
    "#9333ea",
    "#ea580c",
    "#0891b2",
    "#be123c",
    "#4f46e5",
)


def _document(title: str, width: int, height: int, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="chart-title" '
        f'viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
        f'<title id="chart-title">{escape(title)}</title>'
        '<rect width="100%" height="100%" fill="#ffffff"/>'
        f"{body}</svg>"
    )


def _text(x: float, y: float, value: str, size: int = 14, anchor: str = "start", weight: str = "400") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="system-ui,sans-serif" '
        f'font-size="{size}px" text-anchor="{anchor}" font-weight="{weight}" fill="#182230">'
        f"{escape(value)}</text>"
    )


def _empty(title: str, message: str) -> str:
    width, height = 900, 420
    return _document(
        title,
        width,
        height,
        _text(width / 2, 190, title, 22, "middle", "700")
        + _text(width / 2, 230, message, 15, "middle"),
    )


def _grid_and_axes(left: int, top: int, plot_width: int, plot_height: int) -> str:
    pieces = []
    for tick in (0, 25, 50, 75, 100):
        y = top + plot_height - (tick / 100) * plot_height
        pieces.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" '
            'stroke="#e5e7eb" stroke-width="1"/>'
        )
        pieces.append(_text(left - 12, y + 5, str(tick), 12, "end"))
    pieces.append(
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" '
        'stroke="#98a2b3" stroke-width="1.5"/>'
    )
    pieces.append(
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" '
        f'y2="{top + plot_height}" stroke="#98a2b3" stroke-width="1.5"/>'
    )
    return "".join(pieces)


def _date_label(value) -> str:
    return value.strftime("%d/%m") if hasattr(value, "strftime") else str(value)


def plot_grade_evolution(
    evaluations: Sequence,
    exams: Sequence,
    subjects: Sequence,
) -> str:
    """Return an SVG line chart with historical grades grouped by subject."""
    exam_to_subject = {exam.id: exam.subject_id for exam in exams}
    subject_names = {subject.id: subject.name for subject in subjects}
    grouped = defaultdict(lambda: defaultdict(list))

    for evaluation in evaluations:
        subject_id = exam_to_subject.get(evaluation.exam_id)
        name = subject_names.get(subject_id)
        if name is None:
            continue
        grouped[name][evaluation.date].append(evaluation.grade)

    if not grouped:
        return _empty("Evolución de notas", "Aún no hay evaluaciones registradas.")

    width, height = 900, 500
    left, top, right, bottom = 72, 60, 190, 78
    plot_width = width - left - right
    plot_height = height - top - bottom
    all_dates = sorted({day for values in grouped.values() for day in values})
    pieces = [
        _text(width / 2, 30, "Evolución de notas", 22, "middle", "700"),
        _grid_and_axes(left, top, plot_width, plot_height),
        _text(left + plot_width / 2, height - 16, "Fecha", 13, "middle"),
        _text(18, top + plot_height / 2, "Nota", 13, "middle"),
    ]

    max_labels = 7
    step = max(1, (len(all_dates) - 1) // (max_labels - 1)) if len(all_dates) > 1 else 1
    label_indexes = sorted(set(list(range(0, len(all_dates), step)) + [len(all_dates) - 1]))
    for index in label_indexes:
        x = (
            left
            if len(all_dates) == 1
            else left + (index / (len(all_dates) - 1)) * plot_width
        )
        pieces.append(_text(x, top + plot_height + 24, _date_label(all_dates[index]), 12, "middle"))

    for index, name in enumerate(sorted(grouped, key=str.casefold)):
        color = _PALETTE[index % len(_PALETTE)]
        points = []
        for date_index, day in enumerate(sorted(grouped[name])):
            grade = sum(grouped[name][day]) / len(grouped[name][day])
            x = (
                left
                if len(all_dates) == 1
                else left + (all_dates.index(day) / (len(all_dates) - 1)) * plot_width
            )
            y = top + plot_height - (grade / 100) * plot_height
            points.append((x, y))
        point_string = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        pieces.append(
            f'<polyline points="{point_string}" fill="none" stroke="{color}" '
            'stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>'
        )
        for x, y in points:
            pieces.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>')

        legend_y = top + index * 28 + 20
        pieces.append(
            f'<line x1="{left + plot_width + 24}" y1="{legend_y - 5}" '
            f'x2="{left + plot_width + 44}" y2="{legend_y - 5}" stroke="{color}" stroke-width="3"/>'
        )
        pieces.append(_text(left + plot_width + 52, legend_y, name, 12))

    return _document("Evolución de notas", width, height, "".join(pieces))


def _bar_chart(title: str, names: list[str], values: list[float], unit: str) -> str:
    if not values:
        return _empty(title, f"Aún no hay datos de {unit}.")

    width = 900
    bar_height = 32
    gap = 18
    top = 66
    left = 220
    right = 90
    height = max(420, top + len(names) * (bar_height + gap) + 35)
    plot_width = width - left - right
    maximum = max(values) or 1
    pieces = [_text(width / 2, 32, title, 22, "middle", "700")]

    for index, (name, value) in enumerate(zip(names, values)):
        y = top + index * (bar_height + gap)
        bar_width = (value / maximum) * plot_width
        pieces.append(_text(left - 12, y + 22, name, 13, "end"))
        pieces.append(
            f'<rect x="{left}" y="{y}" width="{bar_width:.1f}" height="{bar_height}" '
            'rx="6" fill="#2563eb"/>'
        )
        pieces.append(_text(min(left + bar_width + 10, width - right), y + 22, f"{value:.1f} {unit}", 13, "start"))

    return _document(title, width, height, "".join(pieces))


def plot_subject_averages(
    subjects: Sequence,
    exams: Sequence,
    evaluations: Sequence,
) -> str:
    """Return an SVG bar chart with each subject's current average."""
    import analyzer

    report = analyzer.build_average_report(subjects, exams, evaluations)
    evaluated = [row for row in report["subjects"] if row["evaluation_count"] > 0]
    ordered = sorted(evaluated, key=lambda row: row["average"])
    return _bar_chart(
        "Promedio por materia",
        [row["subject_name"] for row in ordered],
        [row["average"] for row in ordered],
        "/100",
    )


def plot_study_time(
    tasks: Sequence,
    subjects: Sequence,
) -> str:
    """Return an SVG bar chart with estimated study hours by subject."""
    subject_names = {subject.id: subject.name for subject in subjects}
    totals = defaultdict(int)
    for task in tasks:
        name = subject_names.get(task.subject_id)
        if name is not None:
            totals[name] += task.estimated_minutes

    ordered = sorted(totals.items(), key=lambda item: item[1])
    return _bar_chart(
        "Tiempo de estudio estimado por materia",
        [name for name, _ in ordered],
        [minutes / 60 for _, minutes in ordered],
        "h",
    )
