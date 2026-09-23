"""Dedicated loopback-only E2E server; all accounts live in a temporary SQLite DB."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory


def main():
    with TemporaryDirectory(prefix="synapse-e2e-") as directory:
        path = Path(directory) / "e2e.db"
        os.environ["SYNAPSE_ENV"] = "test"
        os.environ["SYNAPSE_DATABASE_URL"] = f"sqlite+aiosqlite:///{path.as_posix()}"
        os.environ["SYNAPSE_CORS_ORIGINS"] = '["http://127.0.0.1:5180"]'
        os.environ["SYNAPSE_COOKIE_SECURE"] = "false"
        os.environ["SYNAPSE_JWT_SECRET"] = ""
        os.environ["SYNAPSE_FRONTEND_URL"] = "http://127.0.0.1:5180"
        import uvicorn
        from alembic.config import Config
        from sqlalchemy import create_engine, delete
        from sqlalchemy.orm import Session

        from alembic import command
        from app.cli import bootstrap_root, seed_centers
        from app.core import mail
        from app.core.security import password_hasher
        from app.main import create_app
        from app.models import AuthRateBucket, User

        engine = create_engine(f"sqlite:///{path.as_posix()}")
        with engine.begin() as connection:
            backend = Path(__file__).resolve().parents[1]
            config = Config(str(backend / "alembic.ini"))
            config.set_main_option("script_location", str(backend / "alembic"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with Session(engine) as db:
            seed_centers(db)
            bootstrap_root(db, "root@example.com", "e2e-root-password-2026!", "E2E Root")
            db.add(
                User(
                    email="existing-invite@example.com",
                    display_name="Existing invite user",
                    password_hash=password_hasher.hash("e2e-existing-password!"),
                )
            )
            db.commit()
        engine.dispose()
        # Test-only mailbox: installed on this isolated app, never the production app.
        messages = []
        mail.deliver = messages.append
        app = create_app()

        @app.get("/__test/mail")
        def mailbox(email: str):
            return [message.get_content() for message in messages if message["To"] == email]

        @app.post("/__test/reset-rate", status_code=204)
        def reset_test_rate_limits():
            # Only this isolated loopback app has fixture controls, never app.main:app.
            with Session(engine) as db:
                db.execute(delete(AuthRateBucket))
                db.commit()

        uvicorn.run(app, host="127.0.0.1", port=8011, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
