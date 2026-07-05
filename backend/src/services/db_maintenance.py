"""Periodic SQLite WAL maintenance.

The app runs in WAL mode (see ``config/database.py``). A passive auto-checkpoint
cannot truncate the ``-wal`` sidecar while any connection still holds an older
read snapshot, so under the polling UI plus the background scheduler the WAL can
grow without bound -- observed at 9.7 GB against a 2.2 GB main DB.

This job runs ``PRAGMA wal_checkpoint(TRUNCATE)`` on a short interval to flush
committed frames into the main database and shrink the WAL back toward zero. It
deliberately uses a raw ``sqlite3`` connection built from the on-disk path rather
than the Flask-SQLAlchemy engine: APScheduler persists jobs by import path in a
SQLAlchemy jobstore, and a module-level function with no Flask app-context
dependency is both serialization-safe and immune to "working outside of
application context" errors in the scheduler thread.
"""
from __future__ import annotations

import logging
import os
import sqlite3

log = logging.getLogger(__name__)


def _default_db_path() -> str:
    # Mirrors app.py: <backend>/instance/sentinelzero.db. SENTINEL_DB_PATH lets a
    # non-default deployment point maintenance at the same file the app uses.
    instance_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "instance"
    )
    return os.path.abspath(os.path.join(instance_dir, "sentinelzero.db"))


def _db_path() -> str:
    return os.environ.get("SENTINEL_DB_PATH", _default_db_path())


def checkpoint_wal() -> dict[str, int] | None:
    """Truncate the WAL. Returns the PRAGMA result, or None if nothing to do.

    Result tuple is ``(busy, log_frames, checkpointed_frames)``:
    ``busy=1`` means a reader blocked a full truncate this cycle (harmless --
    the next interval retries). Never raises into the scheduler.
    """
    path = _db_path()
    if not os.path.exists(path):
        return None
    conn = None
    try:
        conn = sqlite3.connect(path, timeout=5.0)
        row = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if not row:
            return None
        busy, log_frames, checkpointed = row
        result = {"busy": busy, "wal_frames": log_frames, "checkpointed": checkpointed}
        if busy:
            log.warning("WAL checkpoint blocked by active reader; wal_frames=%s", log_frames)
        return result
    except sqlite3.Error as exc:
        log.warning("WAL checkpoint failed: %s", exc)
        return None
    finally:
        if conn is not None:
            conn.close()
