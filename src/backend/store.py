"""Append-only canonical event store. Raw psycopg3, no ORM."""
import psycopg
from psycopg.rows import dict_row


def get_connection(database_url: str) -> psycopg.Connection:
    conn = psycopg.connect(database_url, row_factory=dict_row, autocommit=True)
    return conn


def init_db(conn: psycopg.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id SERIAL PRIMARY KEY,
            customer_id TEXT,
            channel TEXT NOT NULL,
            action TEXT,
            timestamp DOUBLE PRECISION NOT NULL,
            confidence DOUBLE PRECISION NOT NULL,
            method TEXT NOT NULL,
            raw_ref TEXT NOT NULL,
            detail TEXT
        )
    """)


class EventStore:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn
        init_db(self.conn)

    def insert(self, customer_id, channel, action, timestamp, confidence, method, raw_ref, detail) -> int:
        cur = self.conn.execute(
            "INSERT INTO events (customer_id, channel, action, timestamp, confidence, method, raw_ref, detail) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (customer_id, channel, action, timestamp, confidence, method, raw_ref, detail),
        )
        row = cur.fetchone()
        assert row is not None
        return row["id"]

    def all_events(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM events ORDER BY timestamp ASC").fetchall()
        return [dict(r) for r in rows]

    def timeline_for_customer(self, customer_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM events WHERE customer_id = %s ORDER BY timestamp ASC", (customer_id,)
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
