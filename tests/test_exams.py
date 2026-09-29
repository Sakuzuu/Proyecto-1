import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from database import (
    ExamNotFoundError,
    SubjectNotFoundError,
    create_exam,
    create_subject,
    delete_exam,
    get_exam,
    initialize_database,
    list_exams,
    update_exam,
)
from models import Exam, ModelValidationError


class ExamModelTests(unittest.TestCase):
    def test_exam_normalizes_and_accepts_valid_data(self):
        exam = Exam(
            None,
            1,
            "  Parcial 1  ",
            date(2026, 10, 10),
            9,
            30,
        )
        self.assertEqual(exam.name, "Parcial 1")
        self.assertEqual(exam.weight, 30.0)

    def test_exam_rejects_invalid_fields(self):
        invalid_values = [
            {"subject_id": 0},
            {"name": " "},
            {"date": "2026-10-10"},
            {"difficulty": 0},
            {"difficulty": 11},
            {"weight": -1},
            {"weight": 101},
        ]
        base = {
            "subject_id": 1,
            "name": "Examen",
            "date": date(2026, 10, 10),
            "difficulty": 5,
            "weight": 20,
        }
        for change in invalid_values:
            values = base.copy()
            values.update(change)
            with self.subTest(change=change):
                with self.assertRaises(ModelValidationError):
                    Exam(None, **values)


class ExamDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "studyflow_test.db"
        initialize_database(self.db_path)
        self.subject = create_subject("Cálculo", database_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_get_and_persist_exam(self):
        created = create_exam(
            self.subject.id,
            "Parcial 1",
            date(2026, 10, 10),
            8,
            30,
            self.db_path,
        )
        self.assertIsNotNone(created.id)
        self.assertEqual(get_exam(created.id, self.db_path), created)

    def test_create_exam_requires_existing_subject(self):
        with self.assertRaises(SubjectNotFoundError):
            create_exam(
                9999,
                "Examen huérfano",
                date(2026, 10, 10),
                5,
                10,
                self.db_path,
            )

    def test_list_exams_is_ordered_and_filters_by_subject(self):
        other = create_subject("Física", database_path=self.db_path)
        create_exam(
            self.subject.id, "B", date(2026, 10, 12), 5, 20, self.db_path
        )
        create_exam(
            self.subject.id, "A", date(2026, 10, 5), 6, 30, self.db_path
        )
        create_exam(
            other.id, "C", date(2026, 10, 1), 7, 40, self.db_path
        )

        self.assertEqual(
            [exam.name for exam in list_exams(database_path=self.db_path)],
            ["C", "A", "B"],
        )
        self.assertEqual(
            [exam.name for exam in list_exams(self.subject.id, self.db_path)],
            ["A", "B"],
        )

    def test_update_exam(self):
        created = create_exam(
            self.subject.id, "A", date(2026, 10, 1), 4, 10, self.db_path
        )
        updated = update_exam(
            created.id,
            self.subject.id,
            "B",
            date(2026, 10, 8),
            9,
            50,
            self.db_path,
        )
        self.assertEqual(get_exam(created.id, self.db_path), updated)

    def test_update_missing_exam_is_rejected(self):
        with self.assertRaises(ExamNotFoundError):
            update_exam(
                9999,
                self.subject.id,
                "B",
                date(2026, 10, 8),
                9,
                50,
                self.db_path,
            )

    def test_update_exam_to_missing_subject_is_rejected(self):
        created = create_exam(
            self.subject.id, "A", date(2026, 10, 1), 4, 10, self.db_path
        )
        with self.assertRaises(SubjectNotFoundError):
            update_exam(
                created.id,
                9999,
                "B",
                date(2026, 10, 8),
                9,
                50,
                self.db_path,
            )

    def test_delete_exam(self):
        created = create_exam(
            self.subject.id, "A", date(2026, 10, 1), 4, 10, self.db_path
        )
        delete_exam(created.id, self.db_path)
        with self.assertRaises(ExamNotFoundError):
            get_exam(created.id, self.db_path)

    def test_delete_missing_exam_is_rejected(self):
        with self.assertRaises(ExamNotFoundError):
            delete_exam(9999, self.db_path)

    def test_delete_exam_cascades_evaluation_rows(self):
        created = create_exam(
            self.subject.id, "Parcial", date(2026, 10, 1), 6, 25, self.db_path
        )
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                INSERT INTO evaluations (exam_id, grade, date, evaluation_type)
                VALUES (?, ?, ?, ?)
                """,
                (created.id, 90, "2026-10-01", "exam"),
            )
            connection.commit()

        delete_exam(created.id, self.db_path)

        with sqlite3.connect(self.db_path) as connection:
            remaining = connection.execute(
                "SELECT COUNT(*) FROM evaluations WHERE exam_id = ?",
                (created.id,),
            ).fetchone()[0]
        self.assertEqual(remaining, 0)


if __name__ == "__main__":
    unittest.main()
