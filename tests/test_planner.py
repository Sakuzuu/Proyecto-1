import unittest
from datetime import date, datetime
from types import SimpleNamespace

import planner


class PlannerTests(unittest.TestCase):
    TODAY = date(2026, 9, 29)
    START = datetime(2026, 9, 29, 16, 0)

    def test_priority_completed_task_is_zero(self):
        task = SimpleNamespace(id=1, subject_id=1, name='Hecha', deadline=date(2026, 9, 30), difficulty=10, estimated_minutes=60, progress=100, status='completed')
        self.assertEqual(planner.calculate_priority(task, self.TODAY), 0.0)

    def test_priority_makes_urgent_difficult_items_high(self):
        task = SimpleNamespace(id=1, subject_id=1, name='Parcial', deadline=self.TODAY, difficulty=9, estimated_minutes=120, progress=0, status='pending')
        self.assertGreaterEqual(planner.calculate_priority(task, self.TODAY), 8.5)

    def test_plan_skips_completed_and_overdue_items(self):
        completed = SimpleNamespace(id=1, subject_id=1, name='Terminada', deadline=self.TODAY, difficulty=10, estimated_minutes=120, progress=100, status='completed')
        overdue = SimpleNamespace(id=2, subject_id=1, name='Vencida', deadline=date(2026, 9, 28), difficulty=10, estimated_minutes=120, progress=0, status='pending')
        upcoming = SimpleNamespace(id=3, subject_id=1, name='Futura', deadline=date(2026, 10, 2), difficulty=8, estimated_minutes=90, progress=0, status='pending')
        plan = planner.generate_study_plan([completed, overdue, upcoming], [], 1.5, self.START, today=self.TODAY)
        self.assertTrue(plan)
        self.assertTrue(all(s.source_id == 3 for s in plan))

    def test_deadline_has_priority_as_a_hard_constraint(self):
        due_today = SimpleNamespace(id=1, subject_id=1, name='Hoy', deadline=self.TODAY, difficulty=2, estimated_minutes=30, progress=0, status='pending')
        difficult_later = SimpleNamespace(id=2, subject_id=1, name='Difícil', deadline=date(2026, 10, 10), difficulty=10, estimated_minutes=60, progress=0, status='pending')
        plan = planner.generate_study_plan([difficult_later, due_today], [], 1.5, self.START, today=self.TODAY)
        self.assertEqual(plan[0].source_id, 1)

    def test_plan_never_exceeds_available_minutes(self):
        task = SimpleNamespace(id=3, subject_id=1, name='Grande', deadline=date(2026, 10, 5), difficulty=8, estimated_minutes=400, progress=0, status='pending')
        plan = planner.generate_study_plan([task], [], 2, self.START, today=self.TODAY)
        self.assertEqual(sum(s.minutes for s in plan), 120)
        self.assertLessEqual(sum(s.minutes for s in plan), 2 * 60)

    def test_plan_never_crosses_midnight_for_deadline_today(self):
        task = SimpleNamespace(id=3, subject_id=1, name='Hoy', deadline=self.TODAY, difficulty=8, estimated_minutes=40, progress=0, status='pending')
        plan = planner.generate_study_plan([task], [], 1, datetime(2026, 9, 29, 23, 30), today=self.TODAY)
        self.assertEqual(sum(s.minutes for s in plan), 29)
        self.assertTrue(all(s.end.date() == self.TODAY for s in plan))

    def test_plan_has_maximum_session_length(self):
        task = SimpleNamespace(id=3, subject_id=1, name='Grande', deadline=date(2026, 10, 5), difficulty=8, estimated_minutes=200, progress=0, status='pending')
        plan = planner.generate_study_plan([task], [], 3, self.START, today=self.TODAY)
        self.assertTrue(all(s.minutes <= 80 for s in plan))

    def test_exam_gets_a_preparation_estimate(self):
        exam = SimpleNamespace(id=7, subject_id=2, name='Parcial de Física', date=date(2026, 10, 2), difficulty=7, weight=30)
        self.assertEqual(planner.estimate_exam_minutes(exam), 88)

    def test_ranking_orders_by_priority(self):
        task = SimpleNamespace(id=1, subject_id=1, name='Tarea', deadline=date(2026, 10, 5), difficulty=5, estimated_minutes=60, progress=0, status='pending')
        exam = SimpleNamespace(id=2, subject_id=1, name='Parcial', date=self.TODAY, difficulty=7, weight=40)
        ranked = planner.rank_study_items([task], [exam], self.TODAY)
        self.assertEqual(ranked[0]['kind'], 'exam')

    def test_invalid_hours_are_rejected(self):
        task = SimpleNamespace(id=1, subject_id=1, name='Tarea', deadline=date(2026, 10, 5), difficulty=5, estimated_minutes=60, progress=0, status='pending')
        with self.assertRaises(ValueError):
            planner.generate_study_plan([task], [], 0, self.START, today=self.TODAY)


if __name__ == '__main__':
    unittest.main()
