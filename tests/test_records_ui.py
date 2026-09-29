import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

import database
import web_app


class RecordsAndSubjectsWebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "records.db"
        self.old_db = database.DATABASE_PATH
        database.DATABASE_PATH = self.db

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
                "QUERY_STRING": "",
                "wsgi.input": io.BytesIO(raw),
                "CONTENT_LENGTH": str(len(raw)),
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
            }
        )
        status, headers = [], []

        def start_response(code, response_headers):
            status.append(code)
            headers.extend(response_headers)

        body = b"".join(
            web_app.application(environ, start_response)
        ).decode("utf-8")
        return status[0], dict(headers), body

    def test_subject_registration_creates_persistent_subjects(self):
        status, _, body = self.request(
            "/subjects",
            "POST",
            {"subjects": "Cálculo\nProgramación\nFísica"},
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("Materias guardadas", body)
        self.assertEqual(
            [s.name for s in database.list_subjects(database_path=self.db)],
            ["Cálculo", "Física", "Programación"],
        )

        _, _, dashboard = self.request("/")
        for subject_name in ("Cálculo", "Programación", "Física"):
            self.assertIn(subject_name, dashboard)

    def test_dashboard_has_no_dropdowns_and_uses_visible_lists(self):
        database.create_subject("Programación", target_grade=90, database_path=self.db)
        body = self.request("/")[2]
        self.assertNotIn("<select", body.lower())
        self.assertIn("Agregar materias", body)
        self.assertIn("picker-list", body)
        self.assertIn('type="radio"', body)

    def test_task_can_be_saved_from_subject_list_selection(self):
        subject = database.create_subject(
            "Programación", target_grade=90, database_path=self.db
        )
        payload = {
            "subject_id": subject.id,
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
        tasks = database.list_tasks(database_path=self.db)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].subject_id, subject.id)
        self.assertEqual(tasks[0].name, "Derivadas")

    def test_exam_and_evaluation_can_be_saved_without_dropdowns(self):
        subject = database.create_subject(
            "Programación", target_grade=90, database_path=self.db
        )
        status, _, body = self.request(
            "/exams",
            "POST",
            {
                "subject_id": subject.id,
                "name": "Parcial 1",
                "exam_date": "2026-10-15",
                "difficulty": 7,
                "weight": 20,
            },
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("Examen creado correctamente", body)

        exam = database.list_exams(database_path=self.db)[0]
        status, _, body = self.request(
            "/evaluations",
            "POST",
            {
                "exam_id": exam.id,
                "grade": 91.5,
                "date": "2026-10-10",
                "type": "Examen",
            },
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("Nota guardada correctamente", body)

        evaluations = database.list_evaluations(database_path=self.db)
        self.assertEqual(len(evaluations), 1)
        self.assertEqual(evaluations[0].exam_id, exam.id)
        self.assertEqual(evaluations[0].grade, 91.5)

    def test_evaluation_requires_existing_exam(self):
        status, _, body = self.request(
            "/evaluations",
            "POST",
            {
                "grade": 80,
                "date": "2026-10-10",
                "type": "Quiz",
            },
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("No se pudo guardar la evaluación", body)
        self.assertEqual(
            database.list_evaluations(database_path=self.db), []
        )


if __name__ == "__main__":
    unittest.main()
