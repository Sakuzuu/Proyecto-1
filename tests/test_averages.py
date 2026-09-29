import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import analyzer
import database
import web_app
from database import create_evaluation, create_exam, create_subject, initialize_database
from models import Evaluation, Exam, Subject


class AverageCalculationTests(unittest.TestCase):
    def test_empty_average_is_zero(self):
        self.assertEqual(analyzer.calculate_average([]), 0.0)

    def test_weighted_average(self):
        self.assertEqual(analyzer.calculate_weighted_average([85, 100], [30, 70]), 95.5)

    def test_negative_weight_rejected(self):
        with self.assertRaises(ValueError):
            analyzer.calculate_weighted_average([80, 90], [50, -10])

    def test_report_uses_latest_evaluation_per_exam(self):
        subjects = [Subject(1, "Cálculo", target_grade=90)]
        exams = [
            Exam(1, 1, "Parcial 1", date(2026, 10, 1), 6, 30),
            Exam(2, 1, "Parcial 2", date(2026, 10, 15), 7, 70),
        ]
        evaluations = [
            Evaluation(1, 1, 60, date(2026, 10, 2), "Examen"),
            Evaluation(2, 1, 80, date(2026, 10, 3), "Corrección"),
            Evaluation(3, 2, 90, date(2026, 10, 16), "Examen"),
        ]
        report = analyzer.build_average_report(subjects, exams, evaluations)

        self.assertEqual(report["subjects"][0]["evaluation_count"], 2)
        self.assertEqual(report["subjects"][0]["simple_average"], 85.0)
        self.assertEqual(report["subjects"][0]["average"], 87.0)
        self.assertEqual(report["general_average"], 87.0)


class AverageDatabaseIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "studyflow.db"
        initialize_database(self.db)
        self.math = create_subject("Cálculo", target_grade=90, database_path=self.db)
        self.programming = create_subject("Programación", target_grade=85, database_path=self.db)
        self.exam1 = create_exam(
            self.math.id, "Parcial 1", date(2026, 10, 1), 7, 30, self.db
        )
        self.exam2 = create_exam(
            self.math.id, "Parcial 2", date(2026, 10, 15), 7, 70, self.db
        )
        self.exam3 = create_exam(
            self.programming.id, "Parcial 1", date(2026, 10, 10), 6, 100, self.db
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_database_data_produces_expected_report(self):
        create_evaluation(self.exam1.id, 80, date(2026, 10, 2), "Examen", self.db)
        create_evaluation(self.exam1.id, 90, date(2026, 10, 3), "Corrección", self.db)
        create_evaluation(self.exam2.id, 100, date(2026, 10, 16), "Examen", self.db)
        create_evaluation(self.exam3.id, 70, date(2026, 10, 11), "Examen", self.db)

        report = analyzer.build_average_report(
            database.list_subjects(database_path=self.db),
            database.list_exams(database_path=self.db),
            database.list_evaluations(database_path=self.db),
        )

        self.assertEqual(report["general_average"], 83.5)
        self.assertEqual(report["subjects"][0]["subject_name"], "Cálculo")
        self.assertEqual(report["subjects"][0]["average"], 97.0)
        self.assertEqual(report["subjects"][1]["subject_name"], "Programación")
        self.assertEqual(report["subjects"][1]["average"], 70.0)
        self.assertEqual(report["subjects"][0]["evaluation_count"], 2)

    def test_zero_exam_weights_fall_back_to_arithmetic_mean(self):
        zero_weight_exam = create_exam(
            self.math.id, "Parcial 3", date(2026, 11, 1), 5, 0, self.db
        )
        create_evaluation(zero_weight_exam.id, 50, date(2026, 11, 2), "Quiz", self.db)

        report = analyzer.build_average_report(
            database.list_subjects(database_path=self.db),
            database.list_exams(database_path=self.db),
            database.list_evaluations(database_path=self.db),
        )
        self.assertEqual(report["subjects"][0]["average"], 50.0)


class AverageWebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "web.db"
        self.old_db = database.DATABASE_PATH
        database.DATABASE_PATH = self.db
        subject = create_subject("Programación", target_grade=80, database_path=self.db)
        self.exam = create_exam(
            subject.id, "Parcial", date(2026, 10, 10), 7, 100, self.db
        )
        create_evaluation(self.exam.id, 91.5, date(2026, 10, 10), "Examen", self.db)

    def tearDown(self):
        database.DATABASE_PATH = self.old_db
        self.tmp.cleanup()

    def request(self, path="/"):
        from io import BytesIO
        from wsgiref.util import setup_testing_defaults

        environ = {}
        setup_testing_defaults(environ)
        environ.update(
            {
                "PATH_INFO": path,
                "REQUEST_METHOD": "GET",
                "wsgi.input": BytesIO(b""),
                "CONTENT_LENGTH": "0",
            }
        )
        status = []
        headers = {}

        def start_response(response_status, response_headers):
            status.append(response_status)
            headers.update(response_headers)

        body = b"".join(web_app.application(environ, start_response)).decode("utf-8")
        return status[0], headers, body

    def test_dashboard_shows_average(self):
        status, _, body = self.request()
        self.assertEqual(status, "200 OK")
        self.assertIn("Promedio actual", body)
        self.assertIn("91.5/100", body)
        self.assertIn("Promedios por materia", body)
        self.assertIn("Programación", body)

    def test_average_api(self):
        status, headers, body = self.request("/api/averages")
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        data = json.loads(body)
        self.assertEqual(data["general_average"], 91.5)
        self.assertEqual(data["subjects"][0]["average"], 91.5)


if __name__ == "__main__":
    unittest.main()
