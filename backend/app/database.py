import sqlite3
import os
from contextlib import contextmanager

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "helpdeskx.db")

def get_db_path() -> str:
    return os.environ.get("HELPDESKX_DB_PATH", DB_PATH)

def init_db(db_path: str = None) -> None:
    path = db_path or get_db_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        category TEXT NOT NULL,
        max_capacity INTEGER NOT NULL DEFAULT 8,
        current_rr_index INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
        role TEXT NOT NULL DEFAULT 'agent',
        is_active INTEGER NOT NULL DEFAULT 1,
        max_active_tickets INTEGER NOT NULL DEFAULT 8
    );

    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_number TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        requester_id TEXT NOT NULL,
        requester_name TEXT NOT NULL,
        requester_dept TEXT NOT NULL,
        category TEXT NOT NULL,
        classifier_used TEXT NOT NULL DEFAULT 'HYBRID',
        classifier_confidence REAL NOT NULL DEFAULT 1.0,
        priority TEXT NOT NULL DEFAULT 'MEDIUM',
        status TEXT NOT NULL DEFAULT 'OPEN',
        assigned_agent_id INTEGER REFERENCES agents(id),
        assigned_team_id INTEGER REFERENCES teams(id),
        is_escalated INTEGER NOT NULL DEFAULT 0,
        escalation_reason TEXT,
        is_backup_assigned INTEGER NOT NULL DEFAULT 0,
        priority_overridden INTEGER NOT NULL DEFAULT 0,
        override_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ticket_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
        action TEXT NOT NULL,
        performed_by TEXT NOT NULL,
        details TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS system_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()

@contextmanager
def get_db(db_path: str = None):
    path = db_path or get_db_path()
    conn = sqlite3.connect(path, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
    finally:
        conn.close()
