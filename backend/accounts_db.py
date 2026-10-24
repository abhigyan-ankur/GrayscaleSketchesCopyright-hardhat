"""
accounts_db.py
---------------
SQLite database for Artchain user accounts.

Separate from registry.py (which tracks artworks/certificates).
This tracks WHO is using the platform: email/password login,
linked wallet address, and plagiarism-violation history.

Schema:
    users(
        id INTEGER PRIMARY KEY,
        email TEXT UNIQUE,
        password_hash TEXT,
        wallet_address TEXT,       -- linked after MetaMask connect
        violation_count INTEGER,   -- copies THEY tried to submit, caught
        is_withheld INTEGER,       -- 1 = account locked after 3 violations
        created_at TEXT
    )
"""

import sqlite3
import os
import shutil
from datetime import datetime, timezone

from config import ACCOUNTS_DB, BASE_DIR

DB_PATH = ACCOUNTS_DB

# Earlier versions kept accounts.db next to the code. Import it once so
# existing users keep their accounts.
_LEGACY_DB = os.path.join(BASE_DIR, "accounts.db")
if not os.path.exists(DB_PATH) and os.path.exists(_LEGACY_DB):
    shutil.copy2(_LEGACY_DB, DB_PATH)

VIOLATION_LIMIT = 3


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            wallet_address TEXT,
            violation_count INTEGER NOT NULL DEFAULT 0,
            is_withheld INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def create_user(email: str, password_hash: str) -> dict:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (email.lower().strip(), password_hash, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        user_id = cur.lastrowid
        return get_user_by_id(user_id)
    except sqlite3.IntegrityError:
        raise ValueError("An account with this email already exists.")
    finally:
        conn.close()


def get_user_by_email(email: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def link_wallet(user_id: int, wallet_address: str):
    conn = get_connection()
    conn.execute(
        "UPDATE users SET wallet_address = ? WHERE id = ?",
        (wallet_address, user_id),
    )
    conn.commit()
    conn.close()


def increment_violation(user_id: int) -> dict:
    """
    Increments a user's violation count. If it reaches VIOLATION_LIMIT,
    withholds (locks) their account. Returns the updated user record.
    """
    conn = get_connection()
    conn.execute(
        "UPDATE users SET violation_count = violation_count + 1 WHERE id = ?",
        (user_id,),
    )
    conn.commit()

    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    user = dict(user)

    if user["violation_count"] >= VIOLATION_LIMIT and not user["is_withheld"]:
        conn.execute("UPDATE users SET is_withheld = 1 WHERE id = ?", (user_id,))
        conn.commit()
        user["is_withheld"] = 1

    conn.close()
    return user


init_db()