import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import (
    DuplicateSubjectError,
    SubjectInUseError,
    SubjectNotFoundError,
    create_subject,
    delete_subject,
    get_subject,
    initialize_database,
    list_subjects,
    update_subject,
)
from models import ModelValidationError, Subject


class SubjectModelTests(unittest.TestCase):
    def test_subject_normalizes_text(self):
        subject = Subject(None, "  Cálculo  ", "  Prof. Ana  ", 88)
        self.assertEqual(subject.name, "Cálculo")
        self.assertEqual(subject.professor, "Prof. Ana")
        self.assertEqual(subject.target_grade, 88.0)

    def test_subject_rejects_invalid_name(self):
        with self.assertRaises(ModelValidationError):
            Subject(None, "   ")

    def test_subject_rejects_invalid_target(self):
        with self.assertRaises(ModelValidationError):
            Subject(None, "Física", target_grade=101)


class SubjectDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "studyflow_test.db"
        initialize_database(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_get_and_persist_subject(self):
        created = create_subject("Cálculo", "Prof. Pérez", 90, self.db_path)
        self.assertIsNotNone(created.id)
        loaded = get_subject(created.id, self.db_path)
        self.assertEqual(loaded, created)

    def test_duplicate_names_are_rejected_case_insensitively(self):
        create_subject("Física", database_path=self.db_path)
        with self.assertRaises(DuplicateSubjectError):
            create_subject("  física  ", database_path=self.db_path)

    def test_list_and_search_subjects(self):
        create_subject("Cálculo", database_path=self.db_path)
        create_subject("Programación", database_path=self.db_path)
        create_subject("Física", database_path=self.db_path)
        self.assertEqual(
            [s.name for s in list_subjects(database_path=self.db_path)],
            ["Cálculo", "Física", "Programación"],
        )
        self.assertEqual(
            [s.name for s in list_subjects("pro", self.db_path)],
            ["Programación"],
        )

    def test_update_subject(self):
        created = create_subject("Cálculo", database_path=self.db_path)
        updated = update_subject(
            created.id, "Cálculo II", "Prof. Gómez", 95, self.db_path
        )
        self.assertEqual(updated.id, created.id)
        self.assertEqual(get_subject(created.id, self.db_path).name, "Cálculo II")

    def test_update_missing_subject(self):
        with self.assertRaises(SubjectNotFoundError):
            update_subject(999, "No existe", database_path=self.db_path)

    def test_delete_subject(self):
        created = create_subject("Historia", database_path=self.db_path)
        delete_subject(created.id, self.db_path)
        with self.assertRaises(SubjectNotFoundError):
            get_subject(created.id, self.db_path)

    def test_delete_is_blocked_when_task_exists(self):
        created = create_subject("Biología", database_path=self.db_path)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "CREATE TABLE tasks (id INTEGER PRIMARY KEY, subject_id INTEGER NOT NULL)"
            )
            connection.execute(
                "INSERT INTO tasks (subject_id) VALUES (?)", (created.id,)
            )
        with self.assertRaises(SubjectInUseError):
            delete_subject(created.id, self.db_path)


if __name__ == "__main__":
    unittest.main()
