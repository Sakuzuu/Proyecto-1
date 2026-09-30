import io
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

import database
import web_app
import web_server


class ErrorHandlingWebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "studyflow.db"
        self.old_db = database.DATABASE_PATH
        database.DATABASE_PATH = self.db
        self.subject = database.create_subject("Programación", database_path=self.db)
        self.exam = database.create_exam(
            self.subject.id,
            "Parcial",
            date.today() + timedelta(days=7),
            7,
            30,
            self.db,
        )

    def tearDown(self):
        database.DATABASE_PATH = self.old_db
        self.tmp.cleanup()

    def request(self, app, path="/", method="GET", payload=None, raw_body=None, content_length=None):
        environ = {}
        setup_testing_defaults(environ)
        raw = raw_body if raw_body is not None else urlencode(payload or {}).encode()
        environ.update(
            {
                "PATH_INFO": path,
                "REQUEST_METHOD": method,
                "QUERY_STRING": urlencode(payload or {}) if method == "GET" and payload else "",
                "wsgi.input": io.BytesIO(raw),
                "CONTENT_LENGTH": str(len(raw) if content_length is None else content_length),
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
            }
        )
        status = []
        headers = {}

        def start_response(code, response_headers):
            status.append(code)
            headers.update(response_headers)

        body = b"".join(app(environ, start_response)).decode("utf-8")
        return status[0], headers, body

    def test_blank_required_field_is_reported_without_crashing(self):
        status, _, body = self.request(
            web_app.application,
            "/tasks",
            "POST",
            {
                "subject_id": self.subject.id,
                "name": "",
                "deadline": date.today().isoformat(),
                "difficulty": "5",
                "estimated_minutes": "30",
                "progress": "0",
                "status": "pending",
            },
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("El nombre es obligatorio", body)

    def test_non_numeric_value_is_reported_without_crashing(self):
        status, _, body = self.request(
            web_app.application,
            "/tasks",
            "POST",
            {
                "subject_id": str(self.subject.id),
                "name": "Tarea",
                "deadline": date.today().isoformat(),
                "difficulty": "hola",
                "estimated_minutes": "30",
                "progress": "0",
                "status": "pending",
            },
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("La dificultad debe ser un entero válido", body)

    def test_invalid_date_is_reported_without_crashing(self):
        status, _, body = self.request(
            web_app.application,
            "/exams",
            "POST",
            {
                "subject_id": str(self.subject.id),
                "name": "Examen",
                "exam_date": "2026-99-99",
                "difficulty": "5",
                "weight": "20",
            },
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("La fecha del examen no tiene una fecha válida", body)

    def test_missing_subject_is_reported_without_crashing(self):
        status, _, body = self.request(
            web_app.application,
            "/tasks",
            "POST",
            {
                "subject_id": "999999",
                "name": "Huérfana",
                "deadline": date.today().isoformat(),
                "difficulty": "5",
                "estimated_minutes": "30",
                "progress": "0",
                "status": "pending",
            },
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("Subject with id 999999 was not found", body)

    def test_missing_exam_is_reported_without_crashing(self):
        status, _, body = self.request(
            web_app.application,
            "/evaluations",
            "POST",
            {
                "exam_id": "999999",
                "grade": "90",
                "date": date.today().isoformat(),
                "type": "Examen",
            },
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("Exam with id 999999 was not found", body)

    def test_invalid_plan_hours_returns_json_error(self):
        status, headers, body = self.request(
            web_app.application,
            "/api/study-plan",
            "GET",
            {"hours": "hola"},
        )
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertIn("debe ser un número válido", json.loads(body)["error"])

    def test_analysis_with_no_data_is_still_a_valid_response(self):
        empty_db = self.db.with_name("empty.db")
        old_db = database.DATABASE_PATH
        database.DATABASE_PATH = empty_db
        try:
            status, headers, body = self.request(
                web_server.application,
                "/api/insights",
                "GET",
            )
            self.assertEqual(status, "200 OK")
            self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
            data = json.loads(body)
            self.assertEqual(data["strengths"], [])
            self.assertEqual(len(data["without_data"]), 0)
        finally:
            database.DATABASE_PATH = old_db

    def test_subject_with_dependencies_cannot_be_deleted(self):
        status, _, body = self.request(
            web_app.application,
            f"/subjects/{self.subject.id}/delete",
            "POST",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("cannot be deleted because it has associated data", body)
        self.assertEqual(database.get_subject(self.subject.id, self.db), self.subject)

    def test_subject_without_dependencies_can_be_deleted(self):
        clean_subject = database.create_subject("Física", database_path=self.db)
        status, _, body = self.request(
            web_app.application,
            f"/subjects/{clean_subject.id}/delete",
            "POST",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("Materia eliminada correctamente", body)
        with self.assertRaises(database.SubjectNotFoundError):
            database.get_subject(clean_subject.id, self.db)

    def test_malformed_content_length_is_handled(self):
        status, _, body = self.request(
            web_app.application,
            "/subjects",
            "POST",
            raw_body=b"subjects=Historia",
            content_length="not-a-number",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("tamaño del formulario no es válido", body)

    def test_invalid_utf8_form_is_handled(self):
        status, _, body = self.request(
            web_app.application,
            "/subjects",
            "POST",
            raw_body=b"subjects=\xff",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("texto no válido", body)

    def test_missing_database_is_recreated_by_health_check(self):
        db_path = self.db.with_name("missing.db")
        if db_path.exists():
            db_path.unlink()
        old_db = database.DATABASE_PATH
        database.DATABASE_PATH = db_path
        try:
            status, headers, body = self.request(web_app.application, "/health")
            self.assertEqual(status, "200 OK")
            self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
            self.assertEqual(json.loads(body), {"status": "ok"})
            self.assertTrue(db_path.exists())
        finally:
            database.DATABASE_PATH = old_db

    def test_unexpected_dashboard_failure_becomes_500_page(self):
        original = web_app._dashboard

        def failing_dashboard(*args, **kwargs):
            raise RuntimeError("simulated")

        web_app._dashboard = failing_dashboard
        try:
            status, _, body = self.request(web_app.application, "/")
        finally:
            web_app._dashboard = original

        self.assertEqual(status, "500 Internal Server Error")
        self.assertIn("Error interno", body)
        self.assertIn("Tus datos no se han eliminado", body)


if __name__ == "__main__":
    unittest.main()
