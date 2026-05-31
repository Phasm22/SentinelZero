"""
Database configuration and initialization
"""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Global database instance
db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """Apply durable SQLite PRAGMAs on every new connection.

    Why this exists: scan/telemetry data once lived only in an orphaned -wal
    sidecar because WAL was enabled ad-hoc and never persisted in code. Setting
    PRAGMAs here makes them part of the app, not a manual step:

    - journal_mode=WAL: concurrent readers don't block the writer (good for the
      polling UI + background scheduler under a single eventlet worker).
    - busy_timeout=5000: wait up to 5s for a lock instead of instantly raising
      'database is locked' when the writer and a reader overlap.
    - synchronous=NORMAL: safe with WAL, much faster than FULL for our workload.
    - foreign_keys=ON: enforce referential integrity.

    Guarded so it is a no-op for non-SQLite engines (e.g. the :memory: test DB
    still works; PRAGMAs are harmless there).
    """
    import sqlite3
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def init_db(app):
    """Initialize database with Flask app"""
    db.init_app(app)
    return db
