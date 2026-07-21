import sqlite3
import time


def get_connection(db_path: str = "governance.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            agent_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            amount REAL,
            target_account TEXT,
            decision TEXT NOT NULL,
            reason TEXT NOT NULL,
            latency_ms REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            agent_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            amount REAL,
            target_account TEXT,
            reason TEXT NOT NULL,
            resolved INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()


class AuditLog:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        init_db(self.conn)

    def record(self, agent_id: str, action_type: str, amount: float, target_account: str,
               decision: str, reason: str, latency_ms: float) -> int:
        cur = self.conn.execute(
            "INSERT INTO audit_log (ts, agent_id, action_type, amount, target_account, decision, reason, latency_ms) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (time.time(), agent_id, action_type, amount, target_account, decision, reason, latency_ms),
        )
        self.conn.commit()
        assert cur.lastrowid is not None
        return cur.lastrowid

    def list(self, limit: int = 200) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
