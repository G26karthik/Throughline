"""Append-only canonical event store. Raw sqlite3, no ORM."""
import sqlite3


def get_connection(db_path: str = "throughline.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT,
            channel TEXT NOT NULL,
            action TEXT,
            timestamp REAL NOT NULL,
            confidence REAL NOT NULL,
            method TEXT NOT NULL,
            raw_ref TEXT NOT NULL,
            detail TEXT
        )
    """)
    conn.commit()


class EventStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        init_db(self.conn)

    def insert(self, customer_id, channel, action, timestamp, confidence, method, raw_ref, detail) -> int:
        cur = self.conn.execute(
            "INSERT INTO events (customer_id, channel, action, timestamp, confidence, method, raw_ref, detail) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (customer_id, channel, action, timestamp, confidence, method, raw_ref, detail),
        )
        self.conn.commit()
        assert cur.lastrowid is not None
        return cur.lastrowid

    def all_events(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM events ORDER BY timestamp ASC").fetchall()
        return [dict(r) for r in rows]

    def timeline_for_customer(self, customer_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM events WHERE customer_id = ? ORDER BY timestamp ASC", (customer_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def unresolved_events(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM events WHERE customer_id IS NULL ORDER BY timestamp ASC"
        ).fetchall()
        return [dict(r) for r in rows]

    def known_customer_ids(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT customer_id FROM events WHERE customer_id IS NOT NULL ORDER BY customer_id"
        ).fetchall()
        return [r["customer_id"] for r in rows]
