"""CareLoop — SQLite database setup and schema."""

import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "careloop.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
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
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            completed_at TEXT,
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

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'patient',
            patient_id TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            provider_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            location TEXT,
            location_url TEXT,
            scheduled_at TEXT NOT NULL,
            duration_minutes INTEGER DEFAULT 30,
            status TEXT NOT NULL DEFAULT 'scheduled',
            prep_checklist_json TEXT DEFAULT '[]',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (provider_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS medications (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            frequency TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            prescribed_by TEXT,
            instructions TEXT,
            side_effects TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        );

        CREATE TABLE IF NOT EXISTS medication_logs (
            id TEXT PRIMARY KEY,
            medication_id TEXT NOT NULL,
            patient_id TEXT NOT NULL,
            taken_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'taken',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (medication_id) REFERENCES medications(id),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        );

        CREATE TABLE IF NOT EXISTS symptom_entries (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            pain_level INTEGER DEFAULT 0,
            mood_level INTEGER DEFAULT 5,
            sleep_quality INTEGER DEFAULT 5,
            vitals_json TEXT DEFAULT '{}',
            notes TEXT,
            logged_at TEXT NOT NULL DEFAULT (datetime('now')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            sender_id TEXT NOT NULL,
            receiver_id TEXT NOT NULL,
            patient_id TEXT,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            urgency TEXT NOT NULL DEFAULT 'normal',
            category TEXT NOT NULL DEFAULT 'general',
            read INTEGER NOT NULL DEFAULT 0,
            parent_id TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (sender_id) REFERENCES users(id),
            FOREIGN KEY (receiver_id) REFERENCES users(id),
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (parent_id) REFERENCES messages(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT,
            related_id TEXT,
            related_type TEXT,
            read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS care_team (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            provider_id TEXT NOT NULL,
            provider_name TEXT NOT NULL,
            provider_role TEXT NOT NULL,
            is_primary INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (provider_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            uploaded_by TEXT NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            description TEXT,
            category TEXT NOT NULL DEFAULT 'general',
            status TEXT NOT NULL DEFAULT 'pending',
            reviewed_by TEXT,
            reviewed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (uploaded_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id TEXT,
            details TEXT,
            ip_address TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_settings (
            id TEXT PRIMARY KEY,
            user_id TEXT UNIQUE NOT NULL,
            notification_prefs_json TEXT DEFAULT '{"email":true,"push":true,"appointments":true,"medications":true,"tasks":true,"messages":true}',
            theme TEXT DEFAULT 'dark',
            language TEXT DEFAULT 'en',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS care_plans (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            plan_json TEXT NOT NULL DEFAULT '{}',
            raw_response TEXT,
            prompt_sent TEXT,
            model TEXT DEFAULT 'glm-5.1',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        );

        CREATE INDEX IF NOT EXISTS idx_encounters_patient ON encounters(patient_id);
        CREATE INDEX IF NOT EXISTS idx_analyses_patient ON glm_analyses(patient_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_patient ON tasks(patient_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
        CREATE INDEX IF NOT EXISTS idx_qa_patient ON qa_exchanges(patient_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments(patient_id);
        CREATE INDEX IF NOT EXISTS idx_appointments_scheduled ON appointments(scheduled_at);
        CREATE INDEX IF NOT EXISTS idx_medications_patient ON medications(patient_id);
        CREATE INDEX IF NOT EXISTS idx_med_logs_patient ON medication_logs(patient_id);
        CREATE INDEX IF NOT EXISTS idx_med_logs_med ON medication_logs(medication_id);
        CREATE INDEX IF NOT EXISTS idx_symptoms_patient ON symptom_entries(patient_id);
        CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id);
        CREATE INDEX IF NOT EXISTS idx_messages_receiver ON messages(receiver_id);
        CREATE INDEX IF NOT EXISTS idx_messages_patient ON messages(patient_id);
        CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
        CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read);
        CREATE INDEX IF NOT EXISTS idx_care_team_patient ON care_team(patient_id);
        CREATE INDEX IF NOT EXISTS idx_documents_patient ON documents(patient_id);
        CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
        CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource_type, resource_id);
        CREATE INDEX IF NOT EXISTS idx_care_plans_patient ON care_plans(patient_id);

        CREATE TABLE IF NOT EXISTS api_usage (
            id TEXT PRIMARY KEY,
            call_type TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            cost_cents REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_api_usage_call_type ON api_usage(call_type);
        CREATE INDEX IF NOT EXISTS idx_api_usage_model ON api_usage(model);
        CREATE INDEX IF NOT EXISTS idx_api_usage_created ON api_usage(created_at);
    """)

    _migrate(conn)
    conn.commit()
    conn.close()


def _migrate(conn):
    enc_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(encounters)").fetchall()
    }
    if "structured_summary" not in enc_cols:
        conn.execute("ALTER TABLE encounters ADD COLUMN structured_summary TEXT")

    ana_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(glm_analyses)").fetchall()
    }
    if "followup_suggestions" not in ana_cols:
        conn.execute("ALTER TABLE glm_analyses ADD COLUMN followup_suggestions TEXT")
