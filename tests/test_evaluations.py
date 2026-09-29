import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from wsgiref.util import setup_testing_defaults

import database
import web_app
from database import (
    EvaluationNotFoundError,
    ExamNotFoundError,
    create_evaluation,
    create_exam,
    create_subject,
    delete_evaluation,
    get_evaluation,
    initialize_database,
    list_evaluations,
    update_evaluation,
)
from models import Evaluation, ModelValidationError


class EvaluationModelTests(unittest.TestCase):
    def test_valid_evaluation(self):
        evaluation = Evaluation(None, 1, 87.5, date(2026, 10, 10), "Examen")
        self.assertEqual(evaluation.grade, 87.5)
        self.assertEqual(evaluation.evaluation_type, "Examen")

    def test_invalid_fields(self):
        base = dict(
            exam_id=1,
            grade=80,
            date=date(2026, 10, 10),
            evaluation_type="Quiz",
        )
        invalid = [
            {"exam_id": 0},
            {"grade": -1},
            {"grade": 101},
            {"date": "2026-10-10"},
            {"evaluation_type": " "},
        ]
        for change in invalid:
            values = base.copy()
            values.update(change)
            with self.subTest(change=change), self.assertRaises(ModelValidationError):
                Evaluation(None, **values)


class EvaluationDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "studyflow.db"
        initialize_database(self.db)
        subject = create_subject("Cálculo", database_path=self.db)
        self.exam = create_exam(
            subject.id, "Parcial 1", date(2026, 10, 10), 8, 30, self.db
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_get_persist(self):
        created = create_evaluation(
            self.exam.id, 92.5, date(2026, 10, 10), "Examen", self.db
        )
        self.assertEqual(get_evaluation(created.id, self.db), created)

    def test_missing_exam_rejected(self):
        with self.assertRaises(ExamNotFoundError):
            create_evaluation(9999, 80, date(2026, 10, 10), "Quiz", self.db)

    def test_list_filters_and_orders(self):
        create_evaluation(self.exam.id, 70, date(2026, 10, 12), "Quiz", self.db)
        create_evaluation(self.exam.id, 80, date(2026, 10, 8), "Examen", self.db)
        self.assertEqual(
            [x.grade for x in list_evaluations(self.exam.id, self.db)], [80, 70]
        )

    def test_update(self):
        item = create_evaluation(
            self.exam.id, 70, date(2026, 10, 8), "Quiz", self.db
        )
        updated = update_evaluation(
            item.id, self.exam.id, 95, date(2026, 10, 10), "Examen", self.db
        )
        self.assertEqual(get_evaluation(item.id, self.db), updated)

    def test_update_missing_evaluation_is_rejected(self):
        with self.assertRaises(EvaluationNotFoundError):
            update_evaluation(
                9999, self.exam.id, 95, date(2026, 10, 10), "Examen", self.db
            )

    def test_update_missing_exam_rejected(self):
        item = create_evaluation(
            self.exam.id, 70, date(2026, 10, 8), "Quiz", self.db
        )
        with self.assertRaises(ExamNotFoundError):
            update_evaluation(
                item.id, 9999, 95, date(2026, 10, 10), "Examen", self.db
            )

    def test_delete(self):
        item = create_evaluation(
            self.exam.id, 70, date(2026, 10, 8), "Quiz", self.db
        )
        delete_evaluation(item.id, self.db)
        with self.assertRaises(EvaluationNotFoundError):
            get_evaluation(item.id, self.db)


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "web.db"
        self.old_db = database.DATABASE_PATH
        database.DATABASE_PATH = self.db
        self.subject = create_subject("Programación", database_path=self.db)
        self.exam = create_exam(
            self.subject.id, "Parcial", date(2026, 10, 10), 7, 30, self.db
        )

    def tearDown(self):
        database.DATABASE_PATH = self.old_db
        self.tmp.cleanup()

    def request(self, path="/", method="GET", payload=""):
        environ = {}
        setup_testing_defaults(environ)
        raw = payload.encode("utf-8")
        environ.update(
            {
                "PATH_INFO": path,
                "REQUEST_METHOD": method,
                "wsgi.input": io.BytesIO(raw),
                "CONTENT_LENGTH": str(len(raw)),
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
            }
        )
        status = []
        headers = []

        def start_response(response_status, response_headers):
            status.append(response_status)
            headers.extend(response_headers)

        body = b"".join(web_app.application(environ, start_response)).decode("utf-8")
        return status[0], dict(headers), body

    def test_home_page_is_browser_ready(self):
        status, headers, body = self.request()
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("StudyFlow", body)
        self.assertIn("Registrar evaluación", body)
        self.assertIn("Parcial", body)

    def test_browser_can_register_grade(self):
        status, _, body = self.request(
            "/evaluations",
            "POST",
            f"exam_id={self.exam.id}&grade=91.5&date=2026-10-10&type=Examen",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("Nota guardada correctamente", body)
        self.assertEqual(
            len(database.list_evaluations(database_path=self.db)), 1
        )

    def test_invalid_browser_grade_returns_error(self):
        status, _, body = self.request(
            "/evaluations",
            "POST",
            f"exam_id={self.exam.id}&grade=150&date=2026-10-10&type=Examen",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("No se pudo guardar la evaluación", body)
        self.assertEqual(
            len(database.list_evaluations(database_path=self.db)), 0
        )

    def test_health_endpoint(self):
        status, headers, body = self.request("/health")
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(json.loads(body), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
