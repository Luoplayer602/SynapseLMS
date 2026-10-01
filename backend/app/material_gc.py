"""Daily cleanup of crashed, unreferenced upload files; never removes referenced versions."""

import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.materials import cleanup_orphans


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Delete eligible orphan files")
    arguments = parser.parse_args()
    engine = create_engine(get_settings().database_url)
    try:
        with Session(engine) as db:
            count = cleanup_orphans(db, apply=arguments.apply)
        print(f"orphan_candidates={count} applied={arguments.apply}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
