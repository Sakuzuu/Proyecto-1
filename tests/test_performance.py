import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

import analyzer
import database
import web_app


class PerformanceAnalyzerTests(unittest.TestCase):
    def test_trend_requires_two_points(self):
        self.assertEqual(analyzer.detect_trend([80]), "→ Sin datos suficientes")

    def test_trend_reports_upward_change(self):
        self.assertEqual(analyzer.detect_trend([70, 80, 80, 90]), "↑ +13.3%")

    def test_trend_reports_downward_change(self):
        self.assertEqual(analyzer.detect_trend([90, 90, 80, 70]), "↓ -16.7%")

    def test_performance_report_selects_best_and_lowest(self):
        from types import SimpleNamespace
        subjects = [
            SimpleNamespace(id=1, name="Programación", target_grade=90),
            SimpleNamespace(id=2, name="Física", target_grade=85),
        ]
        exams = [
            SimpleNamespace(id=1, subject_id=1, name="P1", date=date(2026, 10, 1), difficulty=5, weight=100),
            SimpleNamespace(id=2, subject_id=2, name="P1", date=date(2026, 10, 1), difficulty=5, weight=100),
        ]
        evaluations = [
            SimpleNamespace(id=1, exam_id=1, grade=80, date=date(2026, 9, 1), evaluation_type="Examen"),
            SimpleNamespace(id=2, exam_id=1, grade=90, date=date(2026, 9, 20), evaluation_type="Examen"),
            SimpleNamespace(id=3, exam_id=2, grade=70, date=date(2026, 9, 1), evaluation_type="Examen"),
            SimpleNamespace(id=4, exam_id=2, grade=75, date=date(2026, 9, 20), evaluation_type="Examen"),
        ]
        report = analyzer.build_performance_report(subjects, exams, evaluations)
        self.assertEqual(report["best_subject"]["subject_name"], "Programación")
        self.assertEqual(report["lowest_subject"]["subject_name"], "Física")
        rows = {row["subject_name"]: row for row in report["subjects"]}
        self.assertEqual(rows["Programación"]["trend"], "↑ +12.5%")
        self.assertEqual(rows["Física"]["trend"], "↑ +7.1%")

    def test_performance_report_without_evaluations_is_safe(self):
        from types import SimpleNamespace
        subject = SimpleNamespace(id=1, name="Cálculo", target_grade=90)
        report = analyzer.build_performance_report([subject], [], [])
        self.assertIsNone(report["best_subject"])
        self.assertIsNone(report["lowest_subject"])
        self.assertEqual(report["overall_trend"], "→ Sin datos suficientes")


class WebFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "web.db"
        self.old_db = database.DATABASE_PATH
        database.DATABASE_PATH = self.db
        self.subject = database.create_subject(
            "Programación", target_grade=90, database_path=self.db
        )
        self.exam = database.create_exam(
            self.subject.id, "Parcial", date(2026, 10, 10), 8, 100, self.db
        )

    def tearDown(self):
        database.DATABASE_PATH = self.old_db
        self.tmp.cleanup()

    def request(self, path="/", method="GET", payload=None):
        environ = {}
        setup_testing_defaults(environ)
        raw = urlencode(payload or {}).encode()
        environ.update(
            {
                "PATH_INFO": path,
                "REQUEST_METHOD": method,
                "wsgi.input": io.BytesIO(raw),
                "CONTENT_LENGTH": str(len(raw)),
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
            }
        )
        status, headers = [], {}

        def start_response(code, response_headers):
            status.append(code)
            headers.update(response_headers)

        body = b"".join(web_app.application(environ, start_response)).decode()
        return status[0], headers, body

    def test_dashboard_has_working_forms_and_analysis(self):
        status, _, body = self.request()
        self.assertEqual(status, "200 OK")
        for action in ("/plan", "/tasks", "/exams", "/evaluations", "/analysis"):
            self.assertIn(action, body)
        self.assertIn("Dashboard de rendimiento", body)

    def test_analysis_page(self):
        database.create_evaluation(
            self.exam.id, 84, date(2026, 9, 10), "Examen", self.db
        )
        status, _, body = self.request("/analysis")
        self.assertEqual(status, "200 OK")
        self.assertIn("Mejor materia", body)
        self.assertIn("Menor promedio", body)
        self.assertIn("Tendencia general", body)
        self.assertIn('action="/"', body)

    def test_performance_api(self):
        database.create_evaluation(
            self.exam.id, 80, date(2026, 9, 10), "Quiz", self.db
        )
        database.create_evaluation(
            self.exam.id, 90, date(2026, 9, 20), "Examen", self.db
        )
        status, headers, body = self.request("/api/performance")
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        data = json.loads(body)
        self.assertEqual(data["general_average"], 90.0)
        self.assertEqual(data["best_subject"]["subject_name"], "Programación")
        self.assertIn("↑", data["overall_trend"])

    def test_create_task_button_flow(self):
        payload = {
            "subject_id": self.subject.id,
            "name": "Derivadas",
            "description": "Guía",
            "deadline": "2026-10-02",
            "difficulty": 8,
            "estimated_minutes": 90,
            "progress": 0,
            "status": "pending",
        }
        status, _, body = self.request("/tasks", "POST", payload)
        self.assertEqual(status, "200 OK")
        self.assertIn("Tarea creada correctamente", body)
        self.assertEqual(len(database.list_tasks(database_path=self.db)), 1)

    def test_create_exam_button_flow(self):
        payload = {
            "subject_id": self.subject.id,
            "name": "Parcial 2",
            "exam_date": "2026-10-15",
            "difficulty": 7,
            "weight": 20,
        }
        status, _, body = self.request("/exams", "POST", payload)
        self.assertEqual(status, "200 OK")
        self.assertIn("Examen creado correctamente", body)
        self.assertEqual(len(database.list_exams(database_path=self.db)), 2)

    def test_register_evaluation_button_flow(self):
        payload = {
            "exam_id": self.exam.id,
            "grade": 88.5,
            "date": "2026-09-29",
            "type": "Examen",
        }
        status, _, body = self.request("/evaluations", "POST", payload)
        self.assertEqual(status, "200 OK")
        self.assertIn("Nota guardada correctamente", body)
        self.assertEqual(len(database.list_evaluations(database_path=self.db)), 1)

    def test_plan_button_flow(self):
        database.create_task(
            self.subject.id,
            "Derivadas",
            "",
            date(2026, 10, 2),
            8,
            60,
            0,
            "pending",
            self.db,
        )
        status, _, body = self.request(
            "/plan", "POST", {"hours": 1.5, "start_time": "16:00"}
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("HOY · Plan generado", body)
        self.assertIn("Derivadas", body)

    def test_complete_task_button_flow(self):
        task = database.create_task(
            self.subject.id,
            "Derivadas",
            "",
            date(2026, 10, 2),
            8,
            60,
            0,
            "pending",
            self.db,
        )
        status, _, body = self.request(f"/tasks/{task.id}/complete", "POST", {})
        self.assertEqual(status, "200 OK")
        self.assertIn("Tarea marcada como completada", body)
        self.assertEqual(database.get_task(task.id, self.db).status, "completed")


if __name__ == "__main__":
    unittest.main()
