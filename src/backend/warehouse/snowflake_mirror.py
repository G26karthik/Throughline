"""Snowflake warehouse mirror: exports the canonical Postgres event store to
Snowflake for analytical workloads at production retention/scale. Snowflake
is a mirror, not the primary store -- Postgres stays canonical, this is a
one-way batch export.

Run standalone: python -m src.backend.warehouse.snowflake_mirror
"""
import os

import snowflake.connector

from src.backend.store import get_connection

TABLE = "EVENTS"


def _postgres_events() -> list[dict]:
    conn = get_connection(os.environ["DATABASE_URL"])
    rows = conn.execute("SELECT * FROM events ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mirror() -> int:
    events = _postgres_events()
    database = os.environ["SNOWFLAKE_DATABASE"]
    schema = os.environ["SNOWFLAKE_SCHEMA"]

    sf = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
    )
    try:
        cur = sf.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {database}")
        cur.execute(f"USE DATABASE {database}")
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        cur.execute(f"USE SCHEMA {schema}")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                id INTEGER,
                customer_id STRING,
                channel STRING,
                action STRING,
                timestamp FLOAT,
                confidence FLOAT,
                method STRING,
                raw_ref STRING,
                detail STRING
            )
        """)
        cur.execute(f"TRUNCATE TABLE {TABLE}")

        if events:
            cur.executemany(
                f"INSERT INTO {TABLE} "
                "(id, customer_id, channel, action, timestamp, confidence, method, raw_ref, detail) "
                "VALUES (%(id)s, %(customer_id)s, %(channel)s, %(action)s, %(timestamp)s, "
                "%(confidence)s, %(method)s, %(raw_ref)s, %(detail)s)",
                events,
            )
        sf.commit()
        print(f"mirrored {len(events)} events to {database}.{schema}.{TABLE}")
        return len(events)
    finally:
        sf.close()


if __name__ == "__main__":
    mirror()
