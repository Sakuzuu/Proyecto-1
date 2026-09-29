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
import web_server


class WebServerInsightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "web.db"
        self.old_db = database.DATABASE_PATH
        database.DATABASE_PATH = self.db
        self.subject = database.create_subject("Programación", target_grade=90, database_path=self.db)
        self.exam = database.create_exam(self.subject.id, "Parcial", date(2026, 10, 10), 8, 100, self.db)
        database.create_evaluation(self.exam.id, 94, date(2026, 9, 10), "Examen", self.db)
    def tearDown(self):
        database.DATABASE_PATH = self.old_db
        self.tmp.cleanup()
    def request(self, path, method="GET", payload=None):
        environ = {}
        setup_testing_defaults(environ)
        raw = urlencode(payload or {}).encode()
        environ.update({
            "PATH_INFO": path,
            "REQUEST_METHOD": method,
            "QUERY_STRING": "" if method != "GET" else (urlencode(payload or {}) if payload else ""),
            "wsgi.input": io.BytesIO(raw),
            "CONTENT_LENGTH": str(len(raw)),
            "CONTENT_TYPE": "application/x-www-form-urlencoded",
        })
        status, headers = [], {}
        def start_response(code, response_headers):
            status.append(code)
            headers.update(response_headers)
        body = b"".join(web_server.application(environ, start_response)).decode("utf-8")
        return status[0], headers, body
    def test_analysis_page_uses_custom_thresholds(self):
        status, _, body = self.request("/analysis", payload={"strength": 95, "attention": 80})
        self.assertEqual(status, "200 OK")
        self.assertIn("95", body)
        self.assertIn("80", body)
        self.assertIn("Rendimiento normal", body)
    def test_insights_api(self):
        status, headers, body = self.request("/api/insights", payload={"strength": 95, "attention": 80})
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        data = json.loads(body)
        self.assertEqual(data["normal"][0]["subject_name"], "Programación")
        self.assertEqual(data["thresholds"]["strength"], 95.0)
    def test_invalid_thresholds_return_400(self):
        status, _, body = self.request("/analysis", payload={"strength": 70, "attention": 75})
        self.assertEqual(status, "400 Bad Request")
        self.assertIn("0 ≤ atención", body)
    def test_existing_root_and_health_still_work(self):
        status, _, body = self.request("/")
        self.assertEqual(status, "200 OK")
        self.assertIn("StudyFlow", body)
        status, headers, body = self.request("/health")
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertIn('"status": "ok"', body)
    def test_existing_charts_route_still_works(self):
        status, _, body = self.request("/charts")
        self.assertEqual(status, "200 OK")
        self.assertIn("Visualizaciones académicas", body)


if __name__ == "__main__":
    unittest.main()
