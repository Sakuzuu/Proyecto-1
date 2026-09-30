"""SQLite persistence layer for StudyFlow.

This module is intentionally independent from the user interface so the same
backend can later be consumed by a browser-based web application.
"""
from datetime import date
from pathlib import Path
import os
import sqlite3
from typing import Optional, Union

from models import Evaluation, Exam, Subject, Task

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = Path(
    os.getenv("STUDYFLOW_DATABASE_PATH", str(DATA_DIR / "studyflow.db"))
)
SCHEMA_PATH = BASE_DIR / "schema.sql"

DatabasePath = Union[str, Path]


class DatabaseError(RuntimeError):
    """Base class for StudyFlow database errors."""


class SubjectNotFoundError(DatabaseError):
    """Raised when a requested subject does not exist."""


class DuplicateSubjectError(DatabaseError):
    """Raised when a subject name is already in use."""


class SubjectInUseError(DatabaseError):
    """Raised when a subject cannot be deleted because it has dependent data."""


class TaskNotFoundError(DatabaseError):
    """Raised when a requested task does not exist."""


class ExamNotFoundError(DatabaseError):
    """Raised when a requested exam does not exist."""


class EvaluationNotFoundError(DatabaseError):
    """Raised when a requested evaluation does not exist."""


def get_connection(database_path: DatabasePath = DATABASE_PATH) -> sqlite3.Connection:
    """Return a configured SQLite connection."""
    path = Path(database_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        return connection
    except (OSError, sqlite3.Error) as exc:
        raise DatabaseError("No se pudo abrir la base de datos.") from exc


def initialize_database(database_path: DatabasePath = DATABASE_PATH) -> None:
    """Create the complete relational schema and mark its version."""
    if not SCHEMA_PATH.exists():
        raise DatabaseError(f"Database schema file not found: {SCHEMA_PATH}")
    try:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        with get_connection(database_path) as connection:
            connection.executescript(schema)
            connection.execute("PRAGMA user_version = 1")
            connection.commit()
            # With WAL + FULL synchronous, each write is committed before the
            # connection closes; the context manager then closes it reliably.
    except DatabaseError:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise DatabaseError("No se pudo inicializar la base de datos.") from exc


def get_schema_version(database_path: DatabasePath = DATABASE_PATH) -> int:
    """Return the SQLite schema version."""
    initialize_database(database_path)
    with get_connection(database_path) as connection:
        row = connection.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def _row_to_subject(row: sqlite3.Row) -> Subject:
    return Subject(
        id=int(row["id"]),
        name=row["name"],
        professor=row["professor"],
        target_grade=float(row["target_grade"]),
    )


def _row_to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=int(row["id"]),
        subject_id=int(row["subject_id"]),
        name=row["name"],
        description=row["description"],
        deadline=date.fromisoformat(row["deadline"]),
        difficulty=int(row["difficulty"]),
        estimated_minutes=int(row["estimated_minutes"]),
        progress=int(row["progress"]),
        status=row["status"],
    )


def _row_to_exam(row: sqlite3.Row) -> Exam:
    return Exam(
        id=int(row["id"]),
        subject_id=int(row["subject_id"]),
        name=row["name"],
        date=date.fromisoformat(row["date"]),
        difficulty=int(row["difficulty"]),
        weight=float(row["weight"]),
    )


def _row_to_evaluation(row: sqlite3.Row) -> Evaluation:
    return Evaluation(
        id=int(row["id"]),
        exam_id=int(row["exam_id"]),
        grade=float(row["grade"]),
        date=date.fromisoformat(row["date"]),
        evaluation_type=row["evaluation_type"],
    )


def _ensure_initialized(database_path: DatabasePath) -> None:
    initialize_database(database_path)


def create_subject(
    name: str,
    professor: str = "",
    target_grade: float = 0.0,
    database_path: DatabasePath = DATABASE_PATH,
) -> Subject:
    subject = Subject(id=None, name=name, professor=professor, target_grade=target_grade)
    _ensure_initialized(database_path)
    try:
        with get_connection(database_path) as connection:
            cursor = connection.execute(
                "INSERT INTO subjects (name, professor, target_grade) VALUES (?, ?, ?)",
                (subject.name, subject.professor, subject.target_grade),
            )
            connection.commit()
            subject.id = int(cursor.lastrowid)
            return subject
    except sqlite3.IntegrityError as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise DuplicateSubjectError(
                f"A subject named '{subject.name}' already exists."
            ) from exc
        raise DatabaseError("Could not create the subject.") from exc


def get_subject(
    subject_id: int,
    database_path: DatabasePath = DATABASE_PATH,
) -> Subject:
    if isinstance(subject_id, bool) or not isinstance(subject_id, int) or subject_id <= 0:
        raise ValueError("subject_id must be a positive integer.")
    _ensure_initialized(database_path)
    with get_connection(database_path) as connection:
        row = connection.execute(
            "SELECT id, name, professor, target_grade FROM subjects WHERE id = ?",
            (subject_id,),
        ).fetchone()
    if row is None:
        raise SubjectNotFoundError(f"Subject with id {subject_id} was not found.")
    return _row_to_subject(row)


def list_subjects(
    search: Optional[str] = None,
    database_path: DatabasePath = DATABASE_PATH,
) -> list[Subject]:
    _ensure_initialized(database_path)
    with get_connection(database_path) as connection:
        if search is None:
            rows = connection.execute(
                "SELECT id, name, professor, target_grade "
                "FROM subjects ORDER BY name COLLATE NOCASE"
            ).fetchall()
        else:
            if not isinstance(search, str):
                raise ValueError("search must be a string or None.")
            search = search.strip()
            rows = connection.execute(
                """
                SELECT id, name, professor, target_grade
                FROM subjects
                WHERE name LIKE ? COLLATE NOCASE
                ORDER BY name COLLATE NOCASE
                """,
                (f"%{search}%",),
            ).fetchall()
    return [_row_to_subject(row) for row in rows]


def update_subject(
    subject_id: int,
    name: str,
    professor: str = "",
    target_grade: float = 0.0,
    database_path: DatabasePath = DATABASE_PATH,
) -> Subject:
    if isinstance(subject_id, bool) or not isinstance(subject_id, int) or subject_id <= 0:
        raise ValueError("subject_id must be a positive integer.")
    subject = Subject(id=subject_id, name=name, professor=professor, target_grade=target_grade)
    _ensure_initialized(database_path)
    try:
        with get_connection(database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE subjects
                SET name = ?, professor = ?, target_grade = ?
                WHERE id = ?
                """,
                (subject.name, subject.professor, subject.target_grade, subject_id),
            )
            if cursor.rowcount == 0:
                raise SubjectNotFoundError(f"Subject with id {subject_id} was not found.")
            connection.commit()
    except sqlite3.IntegrityError as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise DuplicateSubjectError(
                f"A subject named '{subject.name}' already exists."
            ) from exc
        raise DatabaseError("Could not update the subject.") from exc
    return subject


def _subject_has_dependencies(connection: sqlite3.Connection, subject_id: int) -> bool:
    for table in ("tasks", "exams"):
        dependency = connection.execute(
            f"SELECT 1 FROM {table} WHERE subject_id = ? LIMIT 1",
            (subject_id,),
        ).fetchone()
        if dependency is not None:
            return True
    return False


def delete_subject(
    subject_id: int,
    database_path: DatabasePath = DATABASE_PATH,
) -> None:
    if isinstance(subject_id, bool) or not isinstance(subject_id, int) or subject_id <= 0:
        raise ValueError("subject_id must be a positive integer.")
    _ensure_initialized(database_path)
    with get_connection(database_path) as connection:
        row = connection.execute(
            "SELECT 1 FROM subjects WHERE id = ?",
            (subject_id,),
        ).fetchone()
        if row is None:
            raise SubjectNotFoundError(f"Subject with id {subject_id} was not found.")
        if _subject_has_dependencies(connection, subject_id):
            raise SubjectInUseError(
                f"Subject with id {subject_id} cannot be deleted because it has associated data."
            )
        try:
            connection.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
            connection.commit()
        except sqlite3.IntegrityError as exc:
            raise SubjectInUseError(
                f"Subject with id {subject_id} cannot be deleted because it has associated data."
            ) from exc


def create_task(
    subject_id: int,
    name: str,
    description: str,
    deadline: date,
    difficulty: int,
    estimated_minutes: int,
    progress: int = 0,
    status: str = "pending",
    database_path: DatabasePath = DATABASE_PATH,
) -> Task:
    task = Task(
        id=None,
        subject_id=subject_id,
        name=name,
        description=description,
        deadline=deadline,
        difficulty=difficulty,
        estimated_minutes=estimated_minutes,
        progress=progress,
        status=status,
    )
    _ensure_initialized(database_path)
    try:
        with get_connection(database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO tasks (
                    subject_id, name, description, deadline, difficulty,
                    estimated_minutes, progress, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.subject_id,
                    task.name,
                    task.description,
                    task.deadline.isoformat(),
                    task.difficulty,
                    task.estimated_minutes,
                    task.progress,
                    task.status,
                ),
            )
            connection.commit()
            task.id = int(cursor.lastrowid)
            return task
    except sqlite3.IntegrityError as exc:
        if "FOREIGN KEY constraint failed" in str(exc):
            raise SubjectNotFoundError(
                f"Subject with id {task.subject_id} was not found."
            ) from exc
        raise DatabaseError("Could not create the task.") from exc


def get_task(task_id: int, database_path: DatabasePath = DATABASE_PATH) -> Task:
    if isinstance(task_id, bool) or not isinstance(task_id, int) or task_id <= 0:
        raise ValueError("task_id must be a positive integer.")
    _ensure_initialized(database_path)
    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT id, subject_id, name, description, deadline, difficulty,
                   estimated_minutes, progress, status
            FROM tasks WHERE id = ?
            """,
            (task_id,),
        ).fetchone()
    if row is None:
        raise TaskNotFoundError(f"Task with id {task_id} was not found.")
    return _row_to_task(row)


def list_tasks(
    subject_id: Optional[int] = None,
    status: Optional[str] = None,
    database_path: DatabasePath = DATABASE_PATH,
) -> list[Task]:
    if subject_id is not None and (
        isinstance(subject_id, bool) or not isinstance(subject_id, int) or subject_id <= 0
    ):
        raise ValueError("subject_id must be a positive integer or None.")
    if status is not None and status not in {"pending", "in_progress", "completed"}:
        raise ValueError("status must be one of: pending, in_progress, completed.")
    _ensure_initialized(database_path)
    clauses = []
    parameters: list[object] = []
    if subject_id is not None:
        clauses.append("subject_id = ?")
        parameters.append(subject_id)
    if status is not None:
        clauses.append("status = ?")
        parameters.append(status)

    query = """
        SELECT id, subject_id, name, description, deadline, difficulty,
               estimated_minutes, progress, status
        FROM tasks
    """
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY deadline ASC, id ASC"

    with get_connection(database_path) as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [_row_to_task(row) for row in rows]


def update_task(
    task_id: int,
    subject_id: int,
    name: str,
    description: str,
    deadline: date,
    difficulty: int,
    estimated_minutes: int,
    progress: int = 0,
    status: str = "pending",
    database_path: DatabasePath = DATABASE_PATH,
) -> Task:
    if isinstance(task_id, bool) or not isinstance(task_id, int) or task_id <= 0:
        raise ValueError("task_id must be a positive integer.")
    task = Task(
        id=task_id,
        subject_id=subject_id,
        name=name,
        description=description,
        deadline=deadline,
        difficulty=difficulty,
        estimated_minutes=estimated_minutes,
        progress=progress,
        status=status,
    )
    _ensure_initialized(database_path)
    try:
        with get_connection(database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE tasks
                SET subject_id = ?, name = ?, description = ?, deadline = ?,
                    difficulty = ?, estimated_minutes = ?, progress = ?, status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    task.subject_id,
                    task.name,
                    task.description,
                    task.deadline.isoformat(),
                    task.difficulty,
                    task.estimated_minutes,
                    task.progress,
                    task.status,
                    task_id,
                ),
            )
            if cursor.rowcount == 0:
                raise TaskNotFoundError(f"Task with id {task_id} was not found.")
            connection.commit()
    except sqlite3.IntegrityError as exc:
        if "FOREIGN KEY constraint failed" in str(exc):
            raise SubjectNotFoundError(
                f"Subject with id {task.subject_id} was not found."
            ) from exc
        raise DatabaseError("Could not update the task.") from exc
    return task


def delete_task(task_id: int, database_path: DatabasePath = DATABASE_PATH) -> None:
    if isinstance(task_id, bool) or not isinstance(task_id, int) or task_id <= 0:
        raise ValueError("task_id must be a positive integer.")
    _ensure_initialized(database_path)
    with get_connection(database_path) as connection:
        cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        if cursor.rowcount == 0:
            raise TaskNotFoundError(f"Task with id {task_id} was not found.")
        connection.commit()


def create_exam(
    subject_id: int,
    name: str,
    exam_date: date,
    difficulty: int,
    weight: float,
    database_path: DatabasePath = DATABASE_PATH,
) -> Exam:
    exam = Exam(
        id=None,
        subject_id=subject_id,
        name=name,
        date=exam_date,
        difficulty=difficulty,
        weight=weight,
    )
    _ensure_initialized(database_path)
    try:
        with get_connection(database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO exams (subject_id, name, date, difficulty, weight)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    exam.subject_id,
                    exam.name,
                    exam.date.isoformat(),
                    exam.difficulty,
                    exam.weight,
                ),
            )
            connection.commit()
            exam.id = int(cursor.lastrowid)
            return exam
    except sqlite3.IntegrityError as exc:
        if "FOREIGN KEY constraint failed" in str(exc):
            raise SubjectNotFoundError(
                f"Subject with id {exam.subject_id} was not found."
            ) from exc
        raise DatabaseError("Could not create the exam.") from exc


def get_exam(exam_id: int, database_path: DatabasePath = DATABASE_PATH) -> Exam:
    if isinstance(exam_id, bool) or not isinstance(exam_id, int) or exam_id <= 0:
        raise ValueError("exam_id must be a positive integer.")
    _ensure_initialized(database_path)
    with get_connection(database_path) as connection:
        row = connection.execute(
            "SELECT id, subject_id, name, date, difficulty, weight "
            "FROM exams WHERE id = ?",
            (exam_id,),
        ).fetchone()
    if row is None:
        raise ExamNotFoundError(f"Exam with id {exam_id} was not found.")
    return _row_to_exam(row)


def list_exams(
    subject_id: Optional[int] = None,
    database_path: DatabasePath = DATABASE_PATH,
) -> list[Exam]:
    if subject_id is not None and (
        isinstance(subject_id, bool) or not isinstance(subject_id, int) or subject_id <= 0
    ):
        raise ValueError("subject_id must be a positive integer or None.")

    _ensure_initialized(database_path)
    if subject_id is None:
        query = """
            SELECT id, subject_id, name, date, difficulty, weight
            FROM exams ORDER BY date ASC, id ASC
        """
        parameters: tuple[object, ...] = ()
    else:
        query = """
            SELECT id, subject_id, name, date, difficulty, weight
            FROM exams
            WHERE subject_id = ?
            ORDER BY date ASC, id ASC
        """
        parameters = (subject_id,)

    with get_connection(database_path) as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [_row_to_exam(row) for row in rows]


def update_exam(
    exam_id: int,
    subject_id: int,
    name: str,
    exam_date: date,
    difficulty: int,
    weight: float,
    database_path: DatabasePath = DATABASE_PATH,
) -> Exam:
    if isinstance(exam_id, bool) or not isinstance(exam_id, int) or exam_id <= 0:
        raise ValueError("exam_id must be a positive integer.")
    exam = Exam(
        id=exam_id,
        subject_id=subject_id,
        name=name,
        date=exam_date,
        difficulty=difficulty,
        weight=weight,
    )
    _ensure_initialized(database_path)
    try:
        with get_connection(database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE exams
                SET subject_id = ?, name = ?, date = ?, difficulty = ?, weight = ?
                WHERE id = ?
                """,
                (
                    exam.subject_id,
                    exam.name,
                    exam.date.isoformat(),
                    exam.difficulty,
                    exam.weight,
                    exam_id,
                ),
            )
            if cursor.rowcount == 0:
                raise ExamNotFoundError(f"Exam with id {exam_id} was not found.")
            connection.commit()
    except sqlite3.IntegrityError as exc:
        if "FOREIGN KEY constraint failed" in str(exc):
            raise SubjectNotFoundError(
                f"Subject with id {exam.subject_id} was not found."
            ) from exc
        raise DatabaseError("Could not update the exam.") from exc
    return exam


def delete_exam(exam_id: int, database_path: DatabasePath = DATABASE_PATH) -> None:
    if isinstance(exam_id, bool) or not isinstance(exam_id, int) or exam_id <= 0:
        raise ValueError("exam_id must be a positive integer.")
    _ensure_initialized(database_path)
    with get_connection(database_path) as connection:
        cursor = connection.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
        if cursor.rowcount == 0:
            raise ExamNotFoundError(f"Exam with id {exam_id} was not found.")
        connection.commit()


def create_evaluation(
    exam_id: int,
    grade: float,
    evaluation_date: date,
    evaluation_type: str,
    database_path: DatabasePath = DATABASE_PATH,
) -> Evaluation:
    """Create and return an evaluation associated with an existing exam."""
    evaluation = Evaluation(
        id=None,
        exam_id=exam_id,
        grade=grade,
        date=evaluation_date,
        evaluation_type=evaluation_type,
    )
    _ensure_initialized(database_path)
    try:
        with get_connection(database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO evaluations (exam_id, grade, date, evaluation_type)
                VALUES (?, ?, ?, ?)
                """,
                (
                    evaluation.exam_id,
                    evaluation.grade,
                    evaluation.date.isoformat(),
                    evaluation.evaluation_type,
                ),
            )
            connection.commit()
            evaluation.id = int(cursor.lastrowid)
            return evaluation
    except sqlite3.IntegrityError as exc:
        if "FOREIGN KEY constraint failed" in str(exc):
            raise ExamNotFoundError(
                f"Exam with id {evaluation.exam_id} was not found."
            ) from exc
        raise DatabaseError("Could not create the evaluation.") from exc


def get_evaluation(
    evaluation_id: int,
    database_path: DatabasePath = DATABASE_PATH,
) -> Evaluation:
    """Return one evaluation by ID."""
    if (
        isinstance(evaluation_id, bool)
        or not isinstance(evaluation_id, int)
        or evaluation_id <= 0
    ):
        raise ValueError("evaluation_id must be a positive integer.")
    _ensure_initialized(database_path)
    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT id, exam_id, grade, date, evaluation_type
            FROM evaluations
            WHERE id = ?
            """,
            (evaluation_id,),
        ).fetchone()
    if row is None:
        raise EvaluationNotFoundError(
            f"Evaluation with id {evaluation_id} was not found."
        )
    return _row_to_evaluation(row)


def list_evaluations(
    exam_id: Optional[int] = None,
    database_path: DatabasePath = DATABASE_PATH,
) -> list[Evaluation]:
    """Return evaluations ordered by date, optionally filtered by exam."""
    if exam_id is not None and (
        isinstance(exam_id, bool) or not isinstance(exam_id, int) or exam_id <= 0
    ):
        raise ValueError("exam_id must be a positive integer or None.")

    _ensure_initialized(database_path)
    if exam_id is None:
        query = """
            SELECT id, exam_id, grade, date, evaluation_type
            FROM evaluations
            ORDER BY date ASC, id ASC
        """
        parameters: tuple[object, ...] = ()
    else:
        query = """
            SELECT id, exam_id, grade, date, evaluation_type
            FROM evaluations
            WHERE exam_id = ?
            ORDER BY date ASC, id ASC
        """
        parameters = (exam_id,)

    with get_connection(database_path) as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [_row_to_evaluation(row) for row in rows]


def update_evaluation(
    evaluation_id: int,
    exam_id: int,
    grade: float,
    evaluation_date: date,
    evaluation_type: str,
    database_path: DatabasePath = DATABASE_PATH,
) -> Evaluation:
    """Update and return an evaluation."""
    if (
        isinstance(evaluation_id, bool)
        or not isinstance(evaluation_id, int)
        or evaluation_id <= 0
    ):
        raise ValueError("evaluation_id must be a positive integer.")

    evaluation = Evaluation(
        id=evaluation_id,
        exam_id=exam_id,
        grade=grade,
        date=evaluation_date,
        evaluation_type=evaluation_type,
    )
    _ensure_initialized(database_path)
    try:
        with get_connection(database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE evaluations
                SET exam_id = ?, grade = ?, date = ?, evaluation_type = ?
                WHERE id = ?
                """,
                (
                    evaluation.exam_id,
                    evaluation.grade,
                    evaluation.date.isoformat(),
                    evaluation.evaluation_type,
                    evaluation_id,
                ),
            )
            if cursor.rowcount == 0:
                raise EvaluationNotFoundError(
                    f"Evaluation with id {evaluation_id} was not found."
                )
            connection.commit()
    except sqlite3.IntegrityError as exc:
        if "FOREIGN KEY constraint failed" in str(exc):
            raise ExamNotFoundError(
                f"Exam with id {evaluation.exam_id} was not found."
            ) from exc
        raise DatabaseError("Could not update the evaluation.") from exc
    return evaluation


def delete_evaluation(
    evaluation_id: int,
    database_path: DatabasePath = DATABASE_PATH,
) -> None:
    """Delete an evaluation by ID."""
    if (
        isinstance(evaluation_id, bool)
        or not isinstance(evaluation_id, int)
        or evaluation_id <= 0
    ):
        raise ValueError("evaluation_id must be a positive integer.")
    _ensure_initialized(database_path)
    with get_connection(database_path) as connection:
        cursor = connection.execute(
            "DELETE FROM evaluations WHERE id = ?", (evaluation_id,)
        )
        if cursor.rowcount == 0:
            raise EvaluationNotFoundError(
                f"Evaluation with id {evaluation_id} was not found."
            )
        connection.commit()
