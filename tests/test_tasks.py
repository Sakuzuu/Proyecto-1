import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from database import (
    SubjectNotFoundError,
    TaskNotFoundError,
    create_subject,
    create_task,
    delete_task,
    get_task,
    initialize_database,
    list_tasks,
    update_task,
)
from models import ModelValidationError, Task


class TaskModelTests(unittest.TestCase):
    def test_task_accepts_valid_data(self):
        task = Task(
            None, 1, "  Derivadas  ", "  Guía  ", date(2026, 10, 2), 8, 120, 40, "in_progress"
        )
        self.assertEqual(task.name, "Derivadas")
        self.assertEqual(task.description, "Guía")
        self.assertEqual(task.progress, 40)
        self.assertEqual(task.status, "in_progress")

    def test_task_rejects_blank_name(self):
        with self.assertRaises(ModelValidationError):
            Task(None, 1, " ", "", date(2026, 10, 2), 5, 30)

    def test_task_rejects_invalid_fields(self):
        invalid = [
            {"subject_id": 0},
            {"difficulty": 0},
            {"difficulty": 11},
            {"estimated_minutes": 0},
            {"progress": -1},
            {"progress": 101},
            {"status": "done"},
            {"deadline": "2026-10-02"},
        ]
        for changes in invalid:
            values = {
                "subject_id": 1,
                "name": "Tarea",
                "description": "",
                "deadline": date(2026, 10, 2),
                "difficulty": 5,
                "estimated_minutes": 30,
                "progress": 0,
                "status": "pending",
            }
            values.update(changes)
            with self.subTest(changes=changes):
                with self.assertRaises(ModelValidationError):
                    Task(None, **values)


class TaskDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "studyflow_test.db"
        initialize_database(self.db_path)
        self.subject = create_subject("Cálculo", database_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_get_and_persist_task(self):
        created = create_task(
            self.subject.id,
            "Derivadas",
            "Resolver ejercicios",
            date(2026, 10, 2),
            8,
            120,
            25,
            "in_progress",
            self.db_path,
        )
        self.assertIsNotNone(created.id)
        loaded = get_task(created.id, self.db_path)
        self.assertEqual(loaded, created)

    def test_create_task_requires_existing_subject(self):
        with self.assertRaises(SubjectNotFoundError):
            create_task(9999, "Huérfana", "", date(2026, 10, 2), 5, 30, database_path=self.db_path)

    def test_list_tasks_filters_by_subject_and_status(self):
        other = create_subject("Física", database_path=self.db_path)
        create_task(self.subject.id, "A", "", date(2026, 10, 3), 5, 30, 0, "pending", self.db_path)
        create_task(self.subject.id, "B", "", date(2026, 10, 1), 6, 60, 50, "in_progress", self.db_path)
        create_task(other.id, "C", "", date(2026, 10, 2), 7, 45, 100, "completed", self.db_path)

        self.assertEqual([task.name for task in list_tasks(database_path=self.db_path)], ["B", "C", "A"])
        self.assertEqual(
            [task.name for task in list_tasks(self.subject.id, "in_progress", self.db_path)],
            ["B"],
        )
        self.assertEqual(
            [task.name for task in list_tasks(status="completed", database_path=self.db_path)],
            ["C"],
        )

    def test_update_task(self):
        created = create_task(
            self.subject.id, "A", "Inicial", date(2026, 10, 3), 4, 30, 0, "pending", self.db_path
        )
        updated = update_task(
            created.id,
            self.subject.id,
            "A final",
            "Actualizada",
            date(2026, 10, 5),
            7,
            90,
            100,
            "completed",
            self.db_path,
        )
        self.assertEqual(updated.id, created.id)
        self.assertEqual(get_task(created.id, self.db_path), updated)

    def test_update_task_to_missing_subject_is_rejected(self):
        created = create_task(
            self.subject.id, "A", "", date(2026, 10, 3), 4, 30, database_path=self.db_path
        )
        with self.assertRaises(SubjectNotFoundError):
            update_task(
                created.id, 9999, "A", "", date(2026, 10, 3), 4, 30, database_path=self.db_path
            )

    def test_delete_task(self):
        created = create_task(
            self.subject.id, "A", "", date(2026, 10, 3), 4, 30, database_path=self.db_path
        )
        delete_task(created.id, self.db_path)
        with self.assertRaises(TaskNotFoundError):
            get_task(created.id, self.db_path)

    def test_delete_missing_task_is_rejected(self):
        with self.assertRaises(TaskNotFoundError):
            delete_task(9999, self.db_path)

    def test_database_constraints_still_protect_tasks(self):
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO tasks (subject_id, name, deadline, difficulty, estimated_minutes) VALUES (?, ?, ?, ?, ?)",
                    (self.subject.id, "Inválida", "2026-10-02", 0, 30),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO tasks (subject_id, name, deadline, difficulty, estimated_minutes) VALUES (?, ?, ?, ?, ?)",
                    (9999, "Huérfana", "2026-10-02", 5, 30),
                )


if __name__ == "__main__":
    unittest.main()
