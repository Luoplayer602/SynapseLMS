from app.db.base import Base
from app.models import Organization, User, UserMembership


def test_foundation_tables_are_registered() -> None:
    assert Organization.__tablename__ in Base.metadata.tables
    assert User.__tablename__ in Base.metadata.tables
    assert UserMembership.__tablename__ in Base.metadata.tables


def test_active_membership_unique_index_exists() -> None:
    membership_table = Base.metadata.tables[UserMembership.__tablename__]
    indexes = {index.name: index for index in membership_table.indexes}

    assert indexes["uq_user_memberships_one_active_per_user"].unique is True

