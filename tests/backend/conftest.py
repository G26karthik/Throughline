import os

import pytest

from src.backend.store import get_connection, init_db

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://throughline:throughline@localhost:5432/throughline_test"
)


@pytest.fixture(autouse=True)
def _clean_events_table():
    conn = get_connection(TEST_DATABASE_URL)
    init_db(conn)
    conn.execute("TRUNCATE TABLE events RESTART IDENTITY")
    conn.close()
    yield
