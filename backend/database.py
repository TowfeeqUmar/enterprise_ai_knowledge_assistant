import sqlite3
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "app.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                file_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                total_chunks INTEGER NOT NULL DEFAULT 0,
                uploaded_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                sources_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()

def save_document(filename: str, file_type: str, size_bytes: int, total_chunks: int):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO documents(filename, file_type, size_bytes, total_chunks, uploaded_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                file_type=excluded.file_type,
                size_bytes=excluded.size_bytes,
                total_chunks=excluded.total_chunks,
                uploaded_at=excluded.uploaded_at
        """, (filename, file_type, size_bytes, total_chunks,
              datetime.now(timezone.utc).isoformat()))
        conn.commit()

def list_documents():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT filename, file_type, size_bytes, total_chunks, uploaded_at "
            "FROM documents ORDER BY uploaded_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]

def delete_document_record(filename: str):
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM documents WHERE filename = ?", (filename,))
        conn.commit()
        return cur.rowcount > 0

def add_chat(question: str, answer: str, sources_json: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO chat_history(question, answer, sources_json, created_at) VALUES (?, ?, ?, ?)",
            (question, answer, sources_json, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()

def get_history(limit: int = 50):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, question, answer, sources_json, created_at "
            "FROM chat_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

def clear_history():
    with get_connection() as conn:
        conn.execute("DELETE FROM chat_history")
        conn.commit()
