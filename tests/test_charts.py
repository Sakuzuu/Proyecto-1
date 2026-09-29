import io
import tempfile
import unittest
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

import database
import charts
import web_app


class ChartFunctionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "charts.db"
        database.initialize_database(self.db)
        self.subject = database.create_subject(
            "Programación", target_grade=90, database_path=self.db
        )
        self.physics = database.create_subject(
            "Física", target_grade=85, database_path=self.db
        )
        self.exam = database.create_exam(
            self.subject.id, "Parcial", date(2026, 10, 1), 7, 100, self.db
        )
        self.exam_physics = database.create_exam(
            self.physics.id, "Parcial", date(2026, 10, 2), 6, 100, self.db
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_grade_evolution_creates_figure(self):
        database.create_evaluation(self.exam.id, 70, date(2026, 9, 1), "Quiz", self.db)
        database.create_evaluation(self.exam.id, 90, date(2026, 9, 20), "Examen", self.db)
        figure = charts.plot_grade_evolution(
            database.list_evaluations(database_path=self.db),
            database.list_exams(database_path=self.db),
            database.list_subjects(database_path=self.db),
        )
        try:
            self.assertEqual(len(figure.axes), 1)
            self.assertEqual(len(figure.axes[0].lines), 1)
            self.assertEqual(len(figure.axes[0].lines[0].get_ydata()), 2)
        finally:
            charts.close_figure(figure)

    def test_subject_averages_creates_one_bar_per_evaluated_subject(self):
        database.create_evaluation(self.exam.id, 80, date(2026, 9, 1), "Examen", self.db)
        database.create_evaluation(
            self.exam_physics.id, 70, date(2026, 9, 2), "Examen", self.db
        )
        figure = charts.plot_subject_averages(
            database.list_subjects(database_path=self.db),
            database.list_exams(database_path=self.db),
            database.list_evaluations(database_path=self.db),
        )
        try:
            self.assertEqual(len(figure.axes[0].patches), 2)
        finally:
            charts.close_figure(figure)

    def test_study_time_aggregates_task_minutes_by_subject(self):
        database.create_task(
            self.subject.id,
            "Algoritmos",
            "",
            date(2026, 10, 5),
            7,
            60,
            database_path=self.db,
        )
        database.create_task(
            self.subject.id,
            "Práctica",
            "",
            date(2026, 10, 6),
            5,
            30,
            database_path=self.db,
        )
        figure = charts.plot_study_time(
            database.list_tasks(database_path=self.db),
            database.list_subjects(database_path=self.db),
        )
        try:
            bars = figure.axes[0].patches
            self.assertEqual(len(bars), 1)
            self.assertAlmostEqual(bars[0].get_width(), 1.5)
        finally:
            charts.close_figure(figure)

    def test_empty_charts_are_renderable(self):
        subjects = database.list_subjects(database_path=self.db)
        exams = database.list_exams(database_path=self.db)
        evaluations = database.list_evaluations(database_path=self.db)
        tasks = database.list_tasks(database_path=self.db)
        figures = [
            charts.plot_grade_evolution(evaluations, exams, subjects),
            charts.plot_subject_averages(subjects, exams, evaluations),
            charts.plot_study_time(tasks, subjects),
        ]
        for figure in figures:
            try:
                self.assertEqual(len(figure.axes), 1)
            finally:
                charts.close_figure(figure)


class ChartWebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "web.db"
        self.old_db = database.DATABASE_PATH
        database.DATABASE_PATH = self.db
        self.subject = database.create_subject(
            "Programación", target_grade=90, database_path=self.db
        )
        self.exam = database.create_exam(
            self.subject.id, "Parcial", date(2026, 10, 1), 7, 100, self.db
        )
        database.create_evaluation(
            self.exam.id, 92, date(2026, 9, 10), "Examen", self.db
        )
        database.create_task(
            self.subject.id,
            "Algoritmos",
            "",
            date(2026, 10, 5),
            7,
            45,
            database_path=self.db,
        )

    def tearDown(self):
        database.DATABASE_PATH = self.old_db
        self.tmp.cleanup()

    def request(self, path="/"):
        environ = {}
        setup_testing_defaults(environ)
        environ.update(
            {
                "PATH_INFO": path,
                "REQUEST_METHOD": "GET",
                "wsgi.input": io.BytesIO(b""),
                "CONTENT_LENGTH": "0",
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
            }
        )
        status, headers = [], {}

        def start_response(code, response_headers):
            status.append(code)
            headers.update(response_headers)

        body = b"".join(web_app.application(environ, start_response))
        return status[0], headers, body

    def test_charts_page_has_all_three_graphs(self):
        status, _, body = self.request("/charts")
        self.assertEqual(status, "200 OK")
        text = body.decode("utf-8")
        self.assertIn('src="/charts/grade-evolution.png"', text)
        self.assertIn('src="/charts/subject-averages.png"', text)
        self.assertIn('src="/charts/study-time.png"', text)
        self.assertIn("Visualizaciones académicas", text)

    def test_dashboard_links_to_charts(self):
        status, _, body = self.request("/")
        self.assertEqual(status, "200 OK")
        self.assertIn('action="/charts"', body.decode("utf-8"))

    def test_chart_image_endpoints_return_png(self):
        for path in (
            "/charts/grade-evolution.png",
            "/charts/subject-averages.png",
            "/charts/study-time.png",
        ):
            status, headers, body = self.request(path)
            self.assertEqual(status, "200 OK")
            self.assertEqual(headers["Content-Type"], "image/png")
            self.assertGreater(len(body), 1000)
            self.assertTrue(body.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_navigation_back_to_analysis(self):
        status, _, body = self.request("/charts")
        self.assertEqual(status, "200 OK")
        self.assertIn('action="/analysis"', body.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
