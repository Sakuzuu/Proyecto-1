import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import (
    SubjectInUseError,
    create_subject,
    delete_subject,
    get_schema_version,
    initialize_database,
)
from models import Subject


class DatabaseSchemaTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "studyflow_test.db"
        initialize_database(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_schema_is_complete_and_versioned(self):
        with sqlite3.connect(self.db_path) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                )
            }
        self.assertEqual(
            tables,
            {"subjects", "tasks", "exams", "evaluations"},
        )
        self.assertEqual(get_schema_version(self.db_path), 1)

    def test_initialization_is_idempotent(self):
        initialize_database(self.db_path)
        initialize_database(self.db_path)
        self.assertEqual(get_schema_version(self.db_path), 1)

    def test_foreign_keys_and_relationships_work(self):
        subject = create_subject("Física", database_path=self.db_path)

        with sqlite3.connect(self.db_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            exam_cursor = connection.execute(
                """
                INSERT INTO exams
                    (subject_id, name, date, difficulty, weight)
                VALUES (?, ?, ?, ?, ?)
                """,
                (subject.id, "Parcial 1", "2026-10-10", 8, 30),
            )
            exam_id = exam_cursor.lastrowid
            connection.execute(
                """
                INSERT INTO evaluations
                    (exam_id, grade, date, evaluation_type)
                VALUES (?, ?, ?, ?)
                """,
                (exam_id, 82, "2026-10-10", "exam"),
            )
            connection.execute(
                """
                INSERT INTO tasks
                    (subject_id, name, description, deadline,
                     difficulty, estimated_minutes, progress, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    subject.id,
                    "Guía",
                    "Ejercicios del parcial",
                    "2026-10-08",
                    7,
                    90,
                    25,
                    "in_progress",
                ),
            )
            connection.commit()

            evaluation_count = connection.execute(
                "SELECT COUNT(*) FROM evaluations"
            ).fetchone()[0]
            task_count = connection.execute(
                "SELECT COUNT(*) FROM tasks"
            ).fetchone()[0]

        self.assertEqual(evaluation_count, 1)
        self.assertEqual(task_count, 1)

    def test_orphan_foreign_keys_are_rejected(self):
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO tasks
                        (subject_id, name, deadline, difficulty, estimated_minutes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (9999, "Huérfana", "2026-10-01", 5, 30),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO exams
                        (subject_id, name, date, difficulty, weight)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (9999, "Huérfano", "2026-10-01", 5, 10),
                )

    def test_column_constraints_are_enforced(self):
        subject = create_subject("Cálculo", database_path=self.db_path)

        invalid_task_values = [
            {"difficulty": 0},
            {"difficulty": 11},
            {"estimated_minutes": 0},
            {"progress": -1},
            {"progress": 101},
            {"status": "done"},
        ]
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            for invalid in invalid_task_values:
                difficulty = invalid.get("difficulty", 5)
                estimated_minutes = invalid.get("estimated_minutes", 60)
                progress = invalid.get("progress", 0)
                status = invalid.get("status", "pending")
                with self.subTest(invalid=invalid):
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(
                            """
                            INSERT INTO tasks
                                (subject_id, name, deadline, difficulty,
                                 estimated_minutes, progress, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                subject.id,
                                "Prueba",
                                "2026-10-01",
                                difficulty,
                                estimated_minutes,
                                progress,
                                status,
                            ),
                        )

            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO exams
                        (subject_id, name, date, difficulty, weight)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (subject.id, "Examen", "2026-10-01", 5, 101),
                )

            exam_id = connection.execute(
                """
                INSERT INTO exams
                    (subject_id, name, date, difficulty, weight)
                VALUES (?, ?, ?, ?, ?)
                """,
                (subject.id, "Examen válido", "2026-10-02", 5, 40),
            ).lastrowid

            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO evaluations
                        (exam_id, grade, date, evaluation_type)
                    VALUES (?, ?, ?, ?)
                    """,
                    (exam_id, 120, "2026-10-02", "exam"),
                )

    def test_exam_deletion_cascades_to_evaluations(self):
        subject = create_subject("Historia", database_path=self.db_path)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            exam_id = connection.execute(
                """
                INSERT INTO exams
                    (subject_id, name, date, difficulty, weight)
                VALUES (?, ?, ?, ?, ?)
                """,
                (subject.id, "Parcial", "2026-10-05", 6, 25),
            ).lastrowid
            connection.execute(
                """
                INSERT INTO evaluations
                    (exam_id, grade, date, evaluation_type)
                VALUES (?, ?, ?, ?)
                """,
                (exam_id, 90, "2026-10-05", "exam"),
            )
            connection.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
            remaining = connection.execute(
                "SELECT COUNT(*) FROM evaluations WHERE exam_id = ?",
                (exam_id,),
            ).fetchone()[0]
        self.assertEqual(remaining, 0)

    def test_subject_deletion_is_protected(self):
        subject = create_subject("Programación", database_path=self.db_path)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                INSERT INTO tasks
                    (subject_id, name, deadline, difficulty, estimated_minutes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (subject.id, "Práctica", "2026-10-03", 4, 45),
            )
            connection.commit()

        with self.assertRaises(SubjectInUseError):
            delete_subject(subject.id, self.db_path)

    def test_existing_subject_model_still_behaves_normally(self):
        subject = Subject(None, "  Física ", " Prof. A ", 85)
        self.assertEqual(subject.name, "Física")
        self.assertEqual(subject.professor, "Prof. A")
        self.assertEqual(subject.target_grade, 85.0)


if __name__ == "__main__":
    unittest.main()
