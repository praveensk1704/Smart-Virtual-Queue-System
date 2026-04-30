"""
Smart Virtual Queue Crowd Control System - Database Models & Logic
Hackathon Demo - Proof of Concept
"""

import sqlite3
import json
import os
import time
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "queue_system.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            face_encoding TEXT,
            group_number INTEGER NOT NULL,
            registered_at TEXT NOT NULL,
            status TEXT DEFAULT 'waiting'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            group_number INTEGER PRIMARY KEY,
            max_members INTEGER DEFAULT 15,
            status TEXT DEFAULT 'waiting'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gate_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            group_number INTEGER,
            action TEXT NOT NULL,
            result TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    # Initialize groups (1-35 as per freedom.md spec)
    for g in range(1, 36):
        cursor.execute(
            "INSERT OR IGNORE INTO groups (group_number, status) VALUES (?, 'waiting')",
            (g,),
        )

    # Initialize system config
    cursor.execute(
        "INSERT OR IGNORE INTO system_config (key, value) VALUES ('active_group', '0')"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO system_config (key, value) VALUES ('gate_status', 'closed')"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO system_config (key, value) VALUES ('system_mode', 'running')"
    )

    conn.commit()
    conn.close()


def get_active_group():
    conn = get_db()
    row = conn.execute(
        "SELECT value FROM system_config WHERE key = 'active_group'"
    ).fetchone()
    conn.close()
    return int(row["value"]) if row else 0


def set_active_group(group_number):
    conn = get_db()
    # Reset previous active group
    conn.execute(
        "UPDATE groups SET status = 'waiting' WHERE status = 'active'"
    )
    # Set new active group
    conn.execute(
        "UPDATE groups SET status = 'active' WHERE group_number = ?",
        (group_number,),
    )
    conn.execute(
        "UPDATE system_config SET value = ? WHERE key = 'active_group'",
        (str(group_number),),
    )
    conn.commit()
    conn.close()


def register_user(name, face_encoding_list):
    conn = get_db()
    cursor = conn.cursor()

    # Find group with fewest members (auto-assign)
    row = cursor.execute("""
        SELECT g.group_number, COUNT(u.id) as member_count
        FROM groups g
        LEFT JOIN users u ON g.group_number = u.group_number
        GROUP BY g.group_number
        HAVING member_count < g.max_members
        ORDER BY member_count ASC, g.group_number ASC
        LIMIT 1
    """).fetchone()

    if not row:
        conn.close()
        return None, "All groups are full"

    group_number = row["group_number"]
    encoding_json = json.dumps(face_encoding_list)

    cursor.execute(
        """INSERT INTO users (name, face_encoding, group_number, registered_at, status)
           VALUES (?, ?, ?, ?, 'waiting')""",
        (name, encoding_json, group_number, datetime.now().isoformat()),
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "user_id": user_id,
        "name": name,
        "group_number": group_number,
    }, None


def get_all_users():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, group_number, registered_at, status FROM users ORDER BY group_number, id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_face_encodings():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, group_number, face_encoding FROM users WHERE face_encoding IS NOT NULL"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "name": r["name"],
            "group_number": r["group_number"],
            "encoding": json.loads(r["face_encoding"]),
        })
    return result


def get_group_stats():
    conn = get_db()
    rows = conn.execute("""
        SELECT g.group_number, g.status, g.max_members, COUNT(u.id) as member_count
        FROM groups g
        LEFT JOIN users u ON g.group_number = u.group_number
        GROUP BY g.group_number
        ORDER BY g.group_number
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_gate_event(user_id, user_name, group_number, action, result):
    conn = get_db()
    conn.execute(
        """INSERT INTO gate_log (user_id, user_name, group_number, action, result, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, user_name, group_number, action, result, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_gate_logs(limit=50):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM gate_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_system_stats():
    conn = get_db()
    total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    active_group = get_active_group()
    total_entries = conn.execute(
        "SELECT COUNT(*) as c FROM gate_log WHERE result = 'granted'"
    ).fetchone()["c"]
    total_denied = conn.execute(
        "SELECT COUNT(*) as c FROM gate_log WHERE result = 'denied'"
    ).fetchone()["c"]
    groups_with_members = conn.execute(
        "SELECT COUNT(DISTINCT group_number) as c FROM users"
    ).fetchone()["c"]
    conn.close()

    return {
        "total_users": total_users,
        "active_group": active_group,
        "total_entries": total_entries,
        "total_denied": total_denied,
        "groups_with_members": groups_with_members,
    }


def reset_system():
    conn = get_db()
    conn.execute("DELETE FROM users")
    conn.execute("DELETE FROM gate_log")
    conn.execute("UPDATE groups SET status = 'waiting'")
    conn.execute("UPDATE system_config SET value = '0' WHERE key = 'active_group'")
    conn.execute("UPDATE system_config SET value = 'closed' WHERE key = 'gate_status'")
    conn.commit()
    conn.close()
