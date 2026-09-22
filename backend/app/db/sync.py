from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

engine = create_engine(
    get_settings().database_url.replace("sqlite+aiosqlite:", "sqlite:"),
    pool_pre_ping=True,
    hide_parameters=True,
)
if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")


session_factory = sessionmaker(engine, expire_on_commit=False)


def get_session():
    with session_factory() as session:
        yield session
