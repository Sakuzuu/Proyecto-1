"""SQLite persistence layer for StudyFlow.

The database layer is intentionally independent from the user interface so the
same backend can later be consumed by a browser-based web application.
"""
from pathlib import Path
import sqlite3
from typing import Optional, Union

from models import Subject

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "studyflow.db"
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


def get_connection(database_path: DatabasePath = DATABASE_PATH) -> sqlite3.Connection:
    """Return a configured SQLite connection.

    A new connection is created per operation, which works well for both the
    current desktop UI and the future HTTP/web UI.
    """
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: DatabasePath = DATABASE_PATH) -> None:
    """Create the complete relational schema and mark its version.

    The operation is idempotent, so it is safe to call when the application
    starts and when an existing database from milestone 2 is opened.
    """
    if not SCHEMA_PATH.exists():
        raise DatabaseError(f"Database schema file not found: {SCHEMA_PATH}")

    with get_connection(database_path) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        connection.execute("PRAGMA user_version = 1")
        connection.commit()


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


def _ensure_initialized(database_path: DatabasePath) -> None:
    initialize_database(database_path)


def create_subject(
    name: str,
    professor: str = "",
    target_grade: float = 0.0,
    database_path: DatabasePath = DATABASE_PATH,
) -> Subject:
    """Create and return a subject, rejecting blank and duplicate names."""
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


def get_subject(subject_id: int, database_path: DatabasePath = DATABASE_PATH) -> Subject:
    """Return one subject by ID."""
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
    """Return all subjects ordered by name, optionally filtering by name."""
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
    """Update and return a subject, validating all new values."""
    if isinstance(subject_id, bool) or not isinstance(subject_id, int) or subject_id <= 0:
        raise ValueError("subject_id must be a positive integer.")
    subject = Subject(
        id=subject_id,
        name=name,
        professor=professor,
        target_grade=target_grade,
    )
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
                raise SubjectNotFoundError(
                    f"Subject with id {subject_id} was not found."
                )
            connection.commit()
    except sqlite3.IntegrityError as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise DuplicateSubjectError(
                f"A subject named '{subject.name}' already exists."
            ) from exc
        raise DatabaseError("Could not update the subject.") from exc
    return subject


def _subject_has_dependencies(connection: sqlite3.Connection, subject_id: int) -> bool:
    """Protect deletion if dependent task or exam rows already exist."""
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
    """Delete a subject only when it has no dependent task or exam records."""
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
