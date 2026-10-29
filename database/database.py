"""Small SQLite persistence layer for the initial ECHOCHAIN bot."""
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = os.getenv("ECHOCHAIN_DB_PATH", "data/echochain.sqlite3")


def connect() -> sqlite3.Connection:
    path = Path(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS artifacts (
            code TEXT PRIMARY KEY,
            creator_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            generation INTEGER NOT NULL DEFAULT 0,
            genome_json TEXT NOT NULL,
            parent_code TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (creator_id) REFERENCES users(telegram_id),
            FOREIGN KEY (parent_code) REFERENCES artifacts(code)
        );
        CREATE TABLE IF NOT EXISTS colonies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            founder_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (founder_id) REFERENCES users(telegram_id)
        );
        CREATE TABLE IF NOT EXISTS colony_members (
            colony_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (colony_id, user_id),
            FOREIGN KEY (colony_id) REFERENCES colonies(id),
            FOREIGN KEY (user_id) REFERENCES users(telegram_id)
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            actor_id INTEGER,
            artifact_code TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_artifacts_creator ON artifacts(creator_id);
        CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
        """)


def remember_user(user_id: int, username: str | None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO users(telegram_id, username) VALUES(?, ?) "
            "ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username",
            (user_id, username),
        )


def add_event(event_type: str, actor_id: int | None = None,
              artifact_code: str | None = None, payload: dict[str, Any] | None = None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO events(event_type, actor_id, artifact_code, payload_json) VALUES(?, ?, ?, ?)",
            (event_type, actor_id, artifact_code, json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)),
        )


def create_artifact(code: str, creator_id: int, name: str, genome: dict[str, int]) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO artifacts(code, creator_id, name, generation, genome_json) VALUES(?, ?, ?, 0, ?)",
            (code, creator_id, name, json.dumps(genome, ensure_ascii=False, sort_keys=True)),
        )
        conn.execute(
            "INSERT INTO events(event_type, actor_id, artifact_code, payload_json) VALUES(?, ?, ?, ?)",
            ("artifact_created", creator_id, code, json.dumps({"name": name, "genome": genome}, ensure_ascii=False, sort_keys=True)),
        )


def get_artifact(code: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM artifacts WHERE code = ?", (code.upper(),)).fetchone()


def list_artifacts(limit: int = 10) -> list[sqlite3.Row]:
    with connect() as conn:
        return list(conn.execute(
            "SELECT * FROM artifacts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall())


def mutate_artifact(code: str, new_genome: dict[str, int], actor_id: int) -> tuple[int, str] | None:
    with connect() as conn:
        row = conn.execute("SELECT generation, name FROM artifacts WHERE code = ?", (code.upper(),)).fetchone()
        if row is None:
            return None
        generation = int(row["generation"]) + 1
        conn.execute(
            "UPDATE artifacts SET generation=?, genome_json=?, updated_at=CURRENT_TIMESTAMP WHERE code=?",
            (generation, json.dumps(new_genome, ensure_ascii=False, sort_keys=True), code.upper()),
        )
        conn.execute(
            "INSERT INTO events(event_type, actor_id, artifact_code, payload_json) VALUES(?, ?, ?, ?)",
            ("artifact_mutated", actor_id, code.upper(),
             json.dumps({"generation": generation, "genome": new_genome}, ensure_ascii=False, sort_keys=True)),
        )
        return generation, str(row["name"])


def create_colony(name: str, founder_id: int) -> tuple[int, bool]:
    clean_name = " ".join(name.split())[:40]
    with connect() as conn:
        existing = conn.execute("SELECT id FROM colonies WHERE name = ?", (clean_name,)).fetchone()
        if existing:
            return int(existing["id"]), False
        cursor = conn.execute("INSERT INTO colonies(name, founder_id) VALUES(?, ?)", (clean_name, founder_id))
        colony_id = int(cursor.lastrowid)
        conn.execute("INSERT INTO colony_members(colony_id, user_id) VALUES(?, ?)", (colony_id, founder_id))
        conn.execute(
            "INSERT INTO events(event_type, actor_id, payload_json) VALUES(?, ?, ?)",
            ("colony_created", founder_id, json.dumps({"name": clean_name}, ensure_ascii=False)),
        )
        return colony_id, True


def list_colonies(limit: int = 10) -> list[sqlite3.Row]:
    with connect() as conn:
        return list(conn.execute(
            "SELECT c.name, COUNT(m.user_id) AS members FROM colonies c "
            "LEFT JOIN colony_members m ON m.colony_id=c.id "
            "GROUP BY c.id ORDER BY c.created_at DESC LIMIT ?", (limit,)
        ).fetchall())


def stats() -> dict[str, int]:
    with connect() as conn:
        return {
            "artifacts": conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0],
            "colonies": conn.execute("SELECT COUNT(*) FROM colonies").fetchone()[0],
            "events": conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        }
