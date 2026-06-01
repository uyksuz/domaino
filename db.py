import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / 'domaino.db'


def _conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS progress (
                length INTEGER PRIMARY KEY,
                offset INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS available_domains (
                domain TEXT PRIMARY KEY,
                found_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()


def get_progress(length):
    with _conn() as conn:
        row = conn.execute(
            'SELECT offset FROM progress WHERE length = ?', (length,)
        ).fetchone()
        return row['offset'] if row else 0


def save_progress(length, offset):
    with _conn() as conn:
        conn.execute('''
            INSERT INTO progress (length, offset, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(length) DO UPDATE SET
                offset = excluded.offset,
                updated_at = excluded.updated_at
        ''', (length, offset))
        conn.commit()


def save_available(domain):
    with _conn() as conn:
        conn.execute(
            'INSERT OR IGNORE INTO available_domains (domain) VALUES (?)', (domain,)
        )
        conn.commit()


def domain_exists(domain):
    """Firebase'e yazmadan önce duplicate kontrolü için."""
    with _conn() as conn:
        row = conn.execute(
            'SELECT 1 FROM available_domains WHERE domain = ?', (domain,)
        ).fetchone()
        return row is not None


def get_all_available():
    with _conn() as conn:
        rows = conn.execute(
            'SELECT domain, found_at FROM available_domains ORDER BY found_at DESC'
        ).fetchall()
        return [dict(row) for row in rows]


def get_total_count():
    with _conn() as conn:
        return conn.execute('SELECT COUNT(*) FROM available_domains').fetchone()[0]


def get_today_domains(today_str: str):
    with _conn() as conn:
        rows = conn.execute(
            'SELECT domain, found_at FROM available_domains WHERE found_at >= ? ORDER BY found_at DESC',
            (today_str,)
        ).fetchall()
        return [dict(row) for row in rows]
