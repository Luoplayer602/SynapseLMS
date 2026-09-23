import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from alembic import command
from app.core.config import get_settings
from app.db.sync import get_session
from app.main import create_app
from app.models import Organization


@pytest.fixture(autouse=True)
def mail_outbox(monkeypatch):
    """No test may accidentally send mail through a developer's SMTP credentials."""
    messages = []
    monkeypatch.setattr("app.core.mail.deliver", messages.append)
    return messages


@pytest.fixture
def api(migrated_engine):
    app = create_app()

    def session_override():
        with Session(migrated_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    with Session(migrated_engine) as db:
        org = Organization(name="Center A", slug="a", is_public=True, registration_enabled=True)
        other = Organization(name="Center B", slug="b", is_public=False, registration_enabled=True)
        db.add_all([org, other])
        db.flush()
        ids = str(org.id), str(other.id)
        db.commit()
    headers = {"X-Synapse-Client": "web", "Origin": "http://localhost:5173"}
    with TestClient(app, headers=headers) as client:
        yield client, migrated_engine, ids, app


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
