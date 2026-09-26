"""Database engine safety tests."""

from sqlmodel import text

from app.db import create_database_engine
from config.settings import Settings


def test_sqlite_connections_enforce_foreign_keys_after_reconnect():
    engine = create_database_engine(
        Settings(database_url="sqlite:///:memory:", testing=True),
        in_memory=True,
    )

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1

    engine.dispose()

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
