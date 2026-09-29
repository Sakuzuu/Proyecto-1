import unittest
from datetime import date
from types import SimpleNamespace

import analyzer


class StrengthWeaknessTests(unittest.TestCase):
    def setUp(self):
        self.subjects = [
            SimpleNamespace(id=1, name="Programación", target_grade=90),
            SimpleNamespace(id=2, name="Cálculo", target_grade=85),
            SimpleNamespace(id=3, name="Física", target_grade=80),
        ]
        self.exams = [
            SimpleNamespace(id=1, subject_id=1, name="P1", date=date(2026, 10, 1), difficulty=5, weight=100),
            SimpleNamespace(id=2, subject_id=2, name="P1", date=date(2026, 10, 1), difficulty=5, weight=100),
            SimpleNamespace(id=3, subject_id=3, name="P1", date=date(2026, 10, 1), difficulty=5, weight=100),
        ]
        self.evaluations = [
            SimpleNamespace(id=1, exam_id=1, grade=92, date=date(2026, 9, 10), evaluation_type="Examen"),
            SimpleNamespace(id=2, exam_id=2, grade=82, date=date(2026, 9, 10), evaluation_type="Examen"),
            SimpleNamespace(id=3, exam_id=3, grade=70, date=date(2026, 9, 10), evaluation_type="Examen"),
        ]

    def test_default_categories(self):
        report = analyzer.detect_strengths_and_weaknesses(self.subjects, self.exams, self.evaluations)
        self.assertEqual([x["subject_name"] for x in report["strengths"]], ["Programación"])
        self.assertEqual([x["subject_name"] for x in report["normal"]], ["Cálculo"])
        self.assertEqual([x["subject_name"] for x in report["attention"]], ["Física"])

    def test_boundaries_are_configurable(self):
        report = analyzer.detect_strengths_and_weaknesses(
            self.subjects[:1],
            self.exams[:1],
            self.evaluations[:1],
            strength_threshold=93,
            attention_threshold=85,
        )
        self.assertEqual(report["normal"][0]["classification"], "normal")

        report = analyzer.detect_strengths_and_weaknesses(
            self.subjects[:1],
            self.exams[:1],
            self.evaluations[:1],
            strength_threshold=93,
            attention_threshold=80,
        )
        self.assertEqual(report["strengths"][0]["classification"], "strength")

    def test_invalid_thresholds_are_rejected(self):
        with self.assertRaises(ValueError):
            analyzer.detect_strengths_and_weaknesses(
                self.subjects, self.exams, self.evaluations,
                strength_threshold=70, attention_threshold=75,
            )
        with self.assertRaises(ValueError):
            analyzer.PerformanceThresholds(101, 75)

    def test_trends_are_returned(self):
        evaluations = list(self.evaluations)
        evaluations.extend([
            SimpleNamespace(id=4, exam_id=3, grade=60, date=date(2026, 9, 20), evaluation_type="Examen"),
            SimpleNamespace(id=5, exam_id=1, grade=96, date=date(2026, 9, 20), evaluation_type="Examen"),
        ])
        report = analyzer.detect_strengths_and_weaknesses(self.subjects, self.exams, evaluations)
        trends = {x["subject_name"]: x["trend_status"] for x in report["trends"]}
        self.assertEqual(trends["Programación"], "up")
        self.assertEqual(trends["Física"], "down")

    def test_subject_without_evaluations_is_safe(self):
        subject = SimpleNamespace(id=4, name="Álgebra", target_grade=80)
        report = analyzer.detect_strengths_and_weaknesses(
            self.subjects + [subject], self.exams, self.evaluations
        )
        self.assertEqual(report["without_data"][0]["subject_name"], "Álgebra")


if __name__ == "__main__":
    unittest.main()
