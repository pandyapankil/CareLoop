"""CareLoop — SQLite database setup and schema."""
import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "careloop.db")


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            date_of_birth TEXT,
            condition TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS encounters (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            author_role TEXT NOT NULL,
            author_name TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        );

        CREATE TABLE IF NOT EXISTS glm_analyses (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            encounter_id TEXT,
            shared_summary TEXT,
            patient_summary TEXT,
            risk_flags_json TEXT DEFAULT '[]',
            tasks_json TEXT DEFAULT '[]',
            trend_summary TEXT,
            raw_response TEXT,
            prompt_sent TEXT,
            model TEXT DEFAULT 'glm-5.1',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (encounter_id) REFERENCES encounters(id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            analysis_id TEXT,
            title TEXT NOT NULL,
            description TEXT,
            owner TEXT NOT NULL DEFAULT 'provider',
            due_window TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (analysis_id) REFERENCES glm_analyses(id)
        );

        CREATE TABLE IF NOT EXISTS qa_exchanges (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            context_used TEXT,
            model TEXT DEFAULT 'glm-5.1',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        );

        CREATE INDEX IF NOT EXISTS idx_encounters_patient ON encounters(patient_id);
        CREATE INDEX IF NOT EXISTS idx_analyses_patient ON glm_analyses(patient_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_patient ON tasks(patient_id);
        CREATE INDEX IF NOT EXISTS idx_qa_patient ON qa_exchanges(patient_id);
    """)

    conn.commit()
    conn.close()
