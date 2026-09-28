-- StudyFlow relational database schema.
-- SQLite 3. Foreign keys are enabled by database.py on every connection.

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    professor TEXT NOT NULL DEFAULT '',
    target_grade REAL NOT NULL DEFAULT 0
        CHECK (target_grade >= 0 AND target_grade <= 100)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    deadline TEXT NOT NULL,
    difficulty INTEGER NOT NULL
        CHECK (difficulty BETWEEN 1 AND 10),
    estimated_minutes INTEGER NOT NULL
        CHECK (estimated_minutes > 0),
    progress INTEGER NOT NULL DEFAULT 0
        CHECK (progress BETWEEN 0 AND 100),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subject_id)
        REFERENCES subjects(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    difficulty INTEGER NOT NULL
        CHECK (difficulty BETWEEN 1 AND 10),
    weight REAL NOT NULL
        CHECK (weight >= 0 AND weight <= 100),
    FOREIGN KEY (subject_id)
        REFERENCES subjects(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL,
    grade REAL NOT NULL
        CHECK (grade >= 0 AND grade <= 100),
    date TEXT NOT NULL,
    evaluation_type TEXT NOT NULL,
    FOREIGN KEY (exam_id)
        REFERENCES exams(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tasks_subject_id
    ON tasks(subject_id);

CREATE INDEX IF NOT EXISTS idx_tasks_deadline
    ON tasks(deadline);

CREATE INDEX IF NOT EXISTS idx_exams_subject_id
    ON exams(subject_id);

CREATE INDEX IF NOT EXISTS idx_exams_date
    ON exams(date);

CREATE INDEX IF NOT EXISTS idx_evaluations_exam_id
    ON evaluations(exam_id);

CREATE INDEX IF NOT EXISTS idx_evaluations_date
    ON evaluations(date);
