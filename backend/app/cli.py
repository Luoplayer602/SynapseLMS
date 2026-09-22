"""Run `python -m app.cli bootstrap-root --email ...` or `seed-centers`."""

import argparse
from getpass import getpass

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select

from app.core.security import password_hasher
from app.db.expressions import EmailKey
from app.db.sync import session_factory
from app.models import Organization, User


def bootstrap_root(db, email, password, display_name):
    email = str(TypeAdapter(EmailStr).validate_python(email.strip())).lower()
    if not 12 <= len(password) <= 128:
        raise ValueError("Password must contain 12–128 characters")
    if db.scalar(select(User.id).where(EmailKey(User.email) == email)):
        raise ValueError("Account already exists; bootstrap never promotes an existing account")
    root = User(
        email=email,
        display_name=display_name,
        password_hash=password_hasher.hash(password),
        is_root_admin=True,
    )
    db.add(root)
    db.commit()
    return root.id


def seed_centers(db):
    from app.core.config import get_settings

    if get_settings().env not in {"development", "test"}:
        raise ValueError("Demo seed is restricted to development/test")
    for slug, name in (("demo-a", "Trung tâm Demo A"), ("demo-b", "Trung tâm Demo B")):
        if not db.scalar(select(Organization.id).where(Organization.slug == slug)):
            db.add(Organization(slug=slug, name=name, is_public=True, registration_enabled=True))
    db.commit()


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    root = commands.add_parser("bootstrap-root")
    root.add_argument("--email", required=True)
    root.add_argument("--name", default="Root Admin")
    commands.add_parser("seed-centers")
    args = parser.parse_args()
    with session_factory() as db:
        if args.command == "bootstrap-root":
            password = getpass("Password (12–128 characters): ")
            if password != getpass("Confirm password: "):
                parser.error("Passwords do not match")
            try:
                bootstrap_root(db, args.email, password, args.name)
            except ValueError as error:
                parser.error(str(error))
            print("Root Admin created.")
        else:
            seed_centers(db)
            print("Demo centers ready. No accounts or passwords were created.")


if __name__ == "__main__":
    main()
