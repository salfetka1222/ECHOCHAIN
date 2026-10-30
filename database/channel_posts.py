"""Atomic operations for owner-approved channel posts."""
from database import database as db


def _ensure_status_column(conn) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(channel_pending_posts)")}
    if "status" not in columns:
        conn.execute(
            "ALTER TABLE channel_pending_posts "
            "ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'"
        )


def claim_pending_channel_post(post_id: int):
    """Atomically reserve a pending post; only one callback can claim it."""
    with db.connect() as conn:
        _ensure_status_column(conn)
        cursor = conn.execute(
            "UPDATE channel_pending_posts SET status='publishing' "
            "WHERE id=? AND status='pending'",
            (post_id,),
        )
        if cursor.rowcount != 1:
            return None
        return conn.execute(
            "SELECT * FROM channel_pending_posts WHERE id=?", (post_id,)
        ).fetchone()


def reject_pending_channel_post(post_id: int) -> bool:
    with db.connect() as conn:
        _ensure_status_column(conn)
        cursor = conn.execute(
            "DELETE FROM channel_pending_posts WHERE id=? AND status='pending'",
            (post_id,),
        )
        return cursor.rowcount == 1


def finish_channel_post(post_id: int) -> bool:
    with db.connect() as conn:
        _ensure_status_column(conn)
        cursor = conn.execute(
            "DELETE FROM channel_pending_posts WHERE id=? AND status='publishing'",
            (post_id,),
        )
        return cursor.rowcount == 1


def release_channel_post(post_id: int) -> bool:
    """Return a failed publication to pending so the owner can retry."""
    with db.connect() as conn:
        _ensure_status_column(conn)
        cursor = conn.execute(
            "UPDATE channel_pending_posts SET status='pending' "
            "WHERE id=? AND status='publishing'",
            (post_id,),
        )
        return cursor.rowcount == 1
