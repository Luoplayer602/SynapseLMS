"""Offline, all-or-nothing AI credential re-encryption during master-key rotation.

Mount both old and new keys privately, stop AI provider traffic, run with --apply,
then switch the Compose secret source to the new key and restart API.
"""

import argparse
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.sync import engine
from app.models import AIProvider
from app.services.ai.providers import decrypt_credential


def rotate(new_key_file: str, *, apply: bool = False) -> int:
    new_key = Fernet(Path(new_key_file).read_bytes().strip())
    with Session(engine) as db:
        providers = list(db.scalars(select(AIProvider).where(
            AIProvider.credential_ciphertext.is_not(None),
        ).order_by(AIProvider.id).with_for_update()))
        replacements = []
        for provider in providers:
            plaintext = decrypt_credential(provider.credential_ciphertext,
                                           get_settings().ai_key_file)
            replacements.append((provider, new_key.encrypt(plaintext.encode()).decode()))
        if apply:
            for provider, ciphertext in replacements:
                provider.credential_ciphertext = ciphertext
                provider.credential_key_version = (provider.credential_key_version or 0) + 1
            db.commit()
        else:
            db.rollback()
    return len(replacements)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rotate encrypted AI provider credentials")
    parser.add_argument("--new-key-file", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    count = rotate(args.new_key_file, apply=args.apply)
    print(f"{'Re-encrypted' if args.apply else 'Verified'} {count} provider credentials")


if __name__ == "__main__":
    main()
