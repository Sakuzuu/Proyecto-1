import io
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

import database
import web_app


class PersistenceAndThemeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "studyflow.db"
        self.old_db = database.DATABASE_PATH
        database.DATABASE_PATH = self.db

    def tearDown(self):
        database.DATABASE_PATH = self.old_db
        self.tmp.cleanup()

    def request(self, path="/", method="GET", payload=None):
        environ = {}
        setup_testing_defaults(environ)
        raw = urlencode(payload or {}).encode("utf-8")
        environ.update(
            {
                "PATH_INFO": path,
                "REQUEST_METHOD": method,
                "QUERY_STRING": urlencode(payload or {}) if method == "GET" else "",
                "wsgi.input": io.BytesIO(raw),
                "CONTENT_LENGTH": str(len(raw)),
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
            }
        )
        status = []
        headers = {}

        def start_response(code, response_headers):
            status.append(code)
            headers.update(response_headers)

        body = b"".join(web_app.application(environ, start_response)).decode("utf-8")
        return status[0], headers, body

    def test_write_is_immediately_persisted_and_reloaded(self):
        subject = database.create_subject("Programación", database_path=self.db)
        task = database.create_task(
            subject.id,
            "Práctica",
            "Persistencia",
            date.today() + timedelta(days=2),
            5,
            45,
            database_path=self.db,
        )
        exam = database.create_exam(
            subject.id,
            "Parcial",
            date.today() + timedelta(days=7),
            7,
            30,
            self.db,
        )
        database.create_evaluation(
            exam.id,
            92,
            date.today(),
            "Examen",
            self.db,
        )

        self.assertTrue(self.db.exists())
        self.assertEqual(database.get_subject(subject.id, self.db).name, "Programación")
        self.assertEqual(database.get_task(task.id, self.db).name, "Práctica")
        self.assertEqual(database.get_exam(exam.id, self.db).name, "Parcial")
        self.assertEqual(database.list_evaluations(database_path=self.db)[0].grade, 92.0)

    def test_persistence_survives_a_new_python_process(self):
        first = (
            "import database; "
            f"database.create_subject('Persistente', database_path=r'{self.db}')"
        )
        subprocess.run([sys.executable, "-c", first], check=True, cwd=str(Path(__file__).resolve().parents[1]))
        second = (
            "import database; "
            f"items=database.list_subjects(database_path=r'{self.db}'); "
            "assert [x.name for x in items] == ['Persistente']"
        )
        subprocess.run([sys.executable, "-c", second], check=True, cwd=str(Path(__file__).resolve().parents[1]))

    def test_database_path_can_be_configured_for_persistent_storage(self):
        key = "STUDYFLOW_DATABASE_PATH"
        previous = os.environ.get(key)
        try:
            os.environ[key] = str(self.db)
            probe = (
                "import database; "
                f"assert str(database.DATABASE_PATH) == r'{self.db}'"
            )
            subprocess.run([sys.executable, "-c", probe], check=True, cwd=str(Path(__file__).resolve().parents[1]))
        finally:
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous

    def test_dark_theme_is_enabled_and_persistent_in_browser(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn('dataset.theme=saved||"dark"', body)
        self.assertIn(':root[data-theme="dark"]', body)
        self.assertIn('localStorage.setItem("studyflow-theme",next)', body)
        self.assertIn('id="theme-toggle"', body)
        self.assertIn("Cambiar tema", body)

    def test_dark_theme_is_present_on_analysis_page(self):
        status, _, body = self.request("/")
        self.assertEqual(status, "200 OK")
        self.assertIn("Cambiar tema", body)


if __name__ == "__main__":
    unittest.main()
