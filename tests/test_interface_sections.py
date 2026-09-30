import io
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

import database
import web_app
import web_server


class InterfaceSectionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "studyflow.db"
        self.old_db = database.DATABASE_PATH
        database.DATABASE_PATH = self.db

    def tearDown(self):
        database.DATABASE_PATH = self.old_db
        self.tmp.cleanup()

    def request(self, application, path="/", method="GET", payload=None):
        environ = {}
        setup_testing_defaults(environ)
        encoded = urlencode(payload or {})
        raw = encoded.encode("utf-8")
        environ.update(
            {
                "PATH_INFO": path,
                "REQUEST_METHOD": method,
                "QUERY_STRING": encoded if method == "GET" else "",
                "wsgi.input": io.BytesIO(raw),
                "CONTENT_LENGTH": str(len(raw)),
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
            }
        )
        captured = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = dict(headers)

        body = b"".join(application(environ, start_response)).decode("utf-8")
        return captured["status"], captured["headers"], body

    def test_homepage_has_three_sections_and_settings(self):
        status, headers, body = self.request(web_app.application)
        self.assertEqual(status, "200 OK")
        self.assertIn("id=\"inicio\"", body)
        self.assertIn("id=\"agregar\"", body)
        self.assertIn("id=\"graficos-plan\"", body)
        self.assertIn("1. Inicio", body)
        self.assertIn("2. Agregar", body)
        self.assertIn("3. Gráficos y plan de estudio", body)
        self.assertIn('id=\"configuracion\"', body)
        self.assertIn('id=\"setting-theme\"', body)
        self.assertIn('id=\"setting-language\"', body)
        self.assertIn('id=\"setting-density\"', body)
        self.assertIn('id=\"setting-motion\"', body)
        self.assertIn('id=\"reset-settings\"', body)
        self.assertIn('studyFlowApplyLanguage', body)
        self.assertIn('studyFlowSave("studyflow-language",document.documentElement.dataset.language)', body)
        self.assertIn('studyFlowSave("studyflow-density",document.documentElement.dataset.density)', body)
        self.assertIn('studyFlowSave("studyflow-reduced-motion",event.target.checked?"true":"false")', body)
        self.assertIn('href="/#inicio"', body)
        self.assertIn('href="/#agregar"', body)
        self.assertIn('href="/#graficos-plan"', body)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")

    def test_homepage_contains_core_content_in_correct_sections(self):
        _, _, body = self.request(web_app.application)
        inicio = body.index('id="inicio"')
        agregar = body.index('id="agregar"')
        graficos = body.index('id="graficos-plan"')
        inicio_part = body[inicio:agregar]
        agregar_part = body[agregar:graficos]
        graficos_part = body[graficos:]
        self.assertIn("Dashboard de rendimiento", inicio_part)
        self.assertIn("Tareas registradas", inicio_part)
        self.assertIn("Exámenes registrados", inicio_part)
        self.assertIn("Evaluaciones registradas", inicio_part)
        self.assertIn('action="/subjects"', agregar_part)
        self.assertIn('action="/tasks"', agregar_part)
        self.assertIn('action="/exams"', agregar_part)
        self.assertIn('action="/evaluations"', agregar_part)
        self.assertIn("/charts/grade-evolution.svg", graficos_part)
        self.assertIn("/charts/subject-averages.svg", graficos_part)
        self.assertIn("/charts/study-time.svg", graficos_part)
        self.assertIn('action="/plan"', graficos_part)

    def test_all_main_form_flows_render_successfully(self):
        future = (date.today() + timedelta(days=3)).isoformat()
        exam_date = (date.today() + timedelta(days=7)).isoformat()

        status, _, body = self.request(
            web_app.application, "/subjects", "POST", {"subjects": "Programación\nCálculo"}
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("Materias guardadas", body)

        subject = database.list_subjects(database_path=self.db)[0]
        status, _, body = self.request(
            web_app.application,
            "/tasks",
            "POST",
            {
                "subject_id": subject.id,
                "name": "Práctica 1",
                "description": "Repaso",
                "deadline": future,
                "difficulty": 5,
                "estimated_minutes": 60,
                "progress": 0,
                "status": "pending",
            },
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("Tarea creada correctamente", body)

        status, _, body = self.request(
            web_app.application,
            "/exams",
            "POST",
            {
                "subject_id": subject.id,
                "name": "Parcial 1",
                "exam_date": exam_date,
                "difficulty": 7,
                "weight": 30,
            },
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("Examen creado correctamente", body)

        exam = database.list_exams(database_path=self.db)[0]
        status, _, body = self.request(
            web_app.application,
            "/evaluations",
            "POST",
            {
                "exam_id": exam.id,
                "grade": 88,
                "date": date.today().isoformat(),
                "type": "Examen",
            },
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("Nota guardada correctamente", body)

        status, _, body = self.request(
            web_app.application,
            "/plan",
            "POST",
            {"hours": "2", "start_time": "18:00"},
        )
        self.assertEqual(status, "200 OK")
        self.assertIn("Plan generado", body)
        self.assertIn("Práctica 1", body)

    def test_secondary_pages_and_chart_endpoints_still_work(self):
        for path in ("/charts", "/analysis"):
            status, _, body = self.request(web_server.application, path)
            self.assertEqual(status, "200 OK", path)
            self.assertIn("StudyFlow", body)
            self.assertIn("Configuración", body)
            self.assertIn('href="/#inicio"', body)

        for path in (
            "/charts/grade-evolution.svg",
            "/charts/subject-averages.svg",
            "/charts/study-time.svg",
        ):
            status, headers, body = self.request(web_app.application, path)
            self.assertEqual(status, "200 OK", path)
            self.assertEqual(headers["Content-Type"], "image/svg+xml; charset=utf-8")
            self.assertIn("<svg", body)

    def test_language_and_preferences_have_real_browser_handlers(self):
        _, _, body = self.request(web_app.application)
        expected = (
            'studyFlowApplyLanguage(event.target.value)',
            'studyFlowApplyTheme(event.target.value)',
            'studyFlowApplyDensity(event.target.value)',
            'studyFlowApplyMotion(event.target.checked)',
            'studyFlowResetSettings',
            'localStorage.removeItem(key)',
            'dataset.reducedMotion',
        )
        for marker in expected:
            self.assertIn(marker, body)


if __name__ == "__main__":
    unittest.main()
