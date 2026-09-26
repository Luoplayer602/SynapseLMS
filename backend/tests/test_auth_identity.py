from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Uuid, insert, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.db.expressions import EmailKey
from app.models import AuthSession, Organization, RefreshToken, User, UserMembership
from tests.conftest import migration_config


def make_user(session, email="student@example.com"):
    user = User(email=email, password_hash="test-only-not-a-real-password-hash")
    session.add(user)
    session.flush()
    return user


def test_normalizes_email_and_rejects_duplicate_raw_insert(migrated_engine):
    with Session(migrated_engine) as session:
        user = make_user(session, "  Student@Example.COM  ")
        assert user.email == "student@example.com"
        session.commit()
        assert (
            session.scalar(select(User.id).where(EmailKey(User.email) == "student@example.com"))
            == user.id
        )
        with pytest.raises(IntegrityError):
            session.execute(
                insert(User.__table__).values(
                    email=" STUDENT@example.com ", password_hash="test-only"
                )
            )
            session.commit()


def test_only_one_active_membership_and_preserve_transfer_history(migrated_engine):
    with Session(migrated_engine) as session:
        user = make_user(session)
        first = Organization(name="First", slug="first")
        second = Organization(name="Second", slug="second")
        session.add_all([first, second])
        session.flush()
        membership = UserMembership(user_id=user.id, organization_id=first.id, role="student")
        session.add(membership)
        session.commit()
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(UserMembership(user_id=user.id, organization_id=second.id, role="teacher"))
            session.flush()
        membership.is_active = False
        membership.ended_at = datetime.now(UTC)
        session.flush()
        session.add(UserMembership(user_id=user.id, organization_id=second.id, role="student"))
        session.commit()
        rows = session.scalars(
            select(UserMembership).where(UserMembership.user_id == user.id)
        ).all()
        assert len(rows) == 2
        assert sum(row.is_active for row in rows) == 1
        assert membership.organization_id == first.id


@pytest.mark.parametrize(
    "role,ended_at",
    [
        ("root_admin", None),
        ("unknown", None),
        ("student", datetime(2026, 1, 1, tzinfo=UTC)),
    ],
)
def test_rejects_invalid_membership(migrated_engine, role, ended_at):
    with Session(migrated_engine) as session:
        user = make_user(session)
        org = Organization(name="Center", slug="center")
        session.add(org)
        session.flush()
        session.add(
            UserMembership(user_id=user.id, organization_id=org.id, role=role, ended_at=ended_at)
        )
        with pytest.raises(IntegrityError):
            session.flush()


def test_root_account_does_not_need_membership(migrated_engine):
    with Session(migrated_engine) as session:
        user = make_user(session)
        user.is_root_admin = True
        session.commit()
        assert session.scalars(select(UserMembership)).all() == []
        assert session.get(User, user.id).is_root_admin


def test_tokens_keep_rotation_history_and_cascade_with_session(migrated_engine):
    now = datetime.now(UTC)
    with Session(migrated_engine) as session:
        user = make_user(session)
        login = AuthSession(user_id=user.id, expires_at=now + timedelta(days=30))
        session.add(login)
        session.flush()
        consumed = RefreshToken(
            session_id=login.id, token_hash="a" * 64, expires_at=login.expires_at, consumed_at=now
        )
        current = RefreshToken(
            session_id=login.id, token_hash="b" * 64, expires_at=login.expires_at
        )
        session.add_all([consumed, current])
        session.commit()
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                RefreshToken(session_id=login.id, token_hash="b" * 64, expires_at=login.expires_at)
            )
            session.flush()
        login.revoked_at = now
        session.commit()
        assert session.get(RefreshToken, consumed.id).consumed_at is not None
        assert session.get(RefreshToken, current.id).consumed_at is None
        session.delete(login)
        session.commit()
        assert session.scalars(select(RefreshToken)).all() == []


def test_session_cannot_reference_missing_user(migrated_engine):
    with Session(migrated_engine) as session:
        session.add(AuthSession(user_id=uuid4(), expires_at=datetime.now(UTC) + timedelta(days=1)))
        with pytest.raises(IntegrityError):
            session.flush()


@pytest.mark.parametrize("invalid", ["session_expired", "token_expired", "short_hash"])
def test_session_and_token_constraints(migrated_engine, invalid):
    now = datetime.now(UTC)
    with Session(migrated_engine) as session:
        user = make_user(session)
        login = AuthSession(user_id=user.id, created_at=now, expires_at=now + timedelta(days=1))
        session.add(login)
        if invalid == "session_expired":
            login.expires_at = now
        else:
            session.flush()
            session.add(
                RefreshToken(
                    session_id=login.id,
                    created_at=now,
                    expires_at=now if invalid == "token_expired" else login.expires_at,
                    token_hash="short" if invalid == "short_hash" else "c" * 64,
                )
            )
        with pytest.raises(IntegrityError):
            session.flush()


def seed_legacy(connection, *, duplicate=False, ended_active=False):
    command.upgrade(migration_config(connection), "20260919_0001")
    # Use reflected tables: the old schema has none of the new ORM fields yet.
    from sqlalchemy import MetaData, Table

    users = Table("users", MetaData(), autoload_with=connection)
    users.c.id.type = Uuid()
    user_id = uuid4()
    connection.execute(
        users.insert().values(
            id=user_id,
            email="Legacy@Example.com",
            password_hash="existing-hash",
            is_active=True,
            is_root_admin=False,
        )
    )
    if duplicate:
        connection.execute(
            users.insert().values(
                id=uuid4(),
                email="legacy@example.com",
                password_hash="another-hash",
                is_active=True,
                is_root_admin=False,
            )
        )
    organizations = Table("organizations", MetaData(), autoload_with=connection)
    organizations.c.id.type = Uuid()
    org_id = uuid4()
    connection.execute(
        organizations.insert().values(id=org_id, name="Existing", slug="existing", is_active=True)
    )
    memberships = Table("user_memberships", MetaData(), autoload_with=connection)
    for name in ("id", "user_id", "organization_id"):
        memberships.c[name].type = Uuid()
    connection.execute(
        memberships.insert().values(
            id=uuid4(),
            user_id=user_id,
            organization_id=org_id,
            role="student",
            is_active=True,
            ended_at=datetime.now(UTC) if ended_active else None,
        )
    )
    return user_id


def test_migration_matches_models(migrated_engine):
    with migrated_engine.begin() as connection:
        command.check(migration_config(connection))


def test_migration_preserves_data_and_roundtrip(database_engine):
    with database_engine.begin() as connection:
        user_id = seed_legacy(connection)
        config = migration_config(connection)
        command.upgrade(config, "head")
        row = connection.execute(select(User.__table__).where(User.id == user_id)).one()
        assert row.email == "Legacy@Example.com"
        assert row.password_hash == "existing-hash"
        assert row.display_name is None
        assert row.email_verified_at is None
        assert connection.scalar(select(UserMembership.role)) == "student"
        assert {"auth_sessions", "refresh_tokens"} <= set(inspect(connection).get_table_names())
        command.downgrade(config, "20260919_0001")
        assert "auth_sessions" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT password_hash FROM users")) == "existing-hash"
        assert connection.scalar(text("SELECT count(*) FROM user_memberships")) == 1
        command.upgrade(config, "head")
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260926_0011"
        # The new normalized uniqueness must still work after downgrade/re-upgrade.
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                insert(User.__table__).values(email="legacy@example.com", password_hash="test-only")
            )


@pytest.mark.parametrize("problem", ["duplicate", "ended_active"])
def test_migration_stops_before_ddl_for_invalid_legacy_data(database_engine, problem):
    with database_engine.begin() as connection:
        seed_legacy(connection, **{problem: True})
        with pytest.raises(RuntimeError):
            command.upgrade(migration_config(connection), "head")
        assert "auth_sessions" not in inspect(connection).get_table_names()
        assert "display_name" not in {
            col["name"] for col in inspect(connection).get_columns("users")
        }
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260919_0001"
