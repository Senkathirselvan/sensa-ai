import os
import sqlite3
from typing import List, Tuple

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "jobs.db")


def init_db() -> None:
    os.makedirs(DB_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                description TEXT,
                status TEXT CHECK(status IN ('SAVED','APPLIED','INTERVIEW','REJECTED')) DEFAULT 'SAVED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)


def save_job_to_db(title: str, company: str, url: str, description: str = "", status: str = "SAVED") -> str:
    init_db()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO jobs (title, company, url, description, status) VALUES (?, ?, ?, ?, ?)",
                (title, company, url, description, status)
            )
        return f"Saved '{title}' at '{company}' with status: {status}."
    except Exception as e:
        return f"Database Error: {str(e)}"


def get_saved_jobs(status: str = "SAVED") -> List[Tuple]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, company, url, status FROM jobs WHERE status = ? ORDER BY id DESC", (status,))
        return cursor.fetchall()


def update_job_status(job_id: int, new_status: str) -> str:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (new_status, job_id))
    return f"Updated Job ID {job_id} to status: {new_status}."
