import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.schema import CreateSchema, DropSchema

from alembic import command
from app.core.config import get_settings


def migration_config(connection):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    config.attributes["connection"] = connection
    return config


@pytest.fixture(
    params=["sqlite", "postgresql"] if os.getenv("SYNAPSE_TEST_POSTGRES") == "1" else ["sqlite"]
)
def database_engine(request, tmp_path):
    """Only the generated test schema is mutated on PostgreSQL; never public."""
    if request.param == "sqlite":
        engine = create_engine(f"sqlite:///{tmp_path / 'identity.db'}")

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        try:
            yield engine
        finally:
            engine.dispose()
        return

    url = get_settings().database_url
    assert url.startswith("postgresql+psycopg://"), "PostgreSQL test requires psycopg URL"
    schema = f"test_auth_{uuid4().hex}"
    admin_engine = create_engine(url)
    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


@pytest.fixture
def migrated_engine(database_engine):
    with database_engine.begin() as connection:
        command.upgrade(migration_config(connection), "head")
    return database_engine
