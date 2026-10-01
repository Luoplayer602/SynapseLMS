from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AIProvider
from app.services.ai.providers import decrypt_credential, validate_base_url
from tests.test_auth_api import login, seed_user

BASE = "/api/v1/ai"


def test_provider_credential_is_encrypted_masked_and_root_only(api, tmp_path, monkeypatch):
    client, engine, (org, _), _ = api
    path = tmp_path / "ai.key"
    path.write_bytes(Fernet.generate_key())
    monkeypatch.setattr(get_settings(), "ai_key_file", str(path))
    seed_user(engine, org, root=True, email="ai-root@example.com")
    seed_user(engine, org, email="ai-manager@example.com")
    root = login(client, "ai-root@example.com")
    manager = login(client, "ai-manager@example.com")
    payload = {
        "code": "primary",
        "name": "Primary",
        "kind": "openai",
        "model_id": "test-model",
        "api_key": "test-key-very-private",
        "allowed_tasks": ["progress_summary"],
        "enabled": True,
    }
    assert client.post(BASE + "/providers", headers=manager, json=payload).status_code == 403
    response = client.post(BASE + "/providers", headers=root, json=payload)
    assert response.status_code == 200, response.text
    assert "test-key-very-private" not in response.text
    assert response.json()["has_key"] is True
    with Session(engine) as db:
        row = db.scalar(select(AIProvider).where(AIProvider.code == "primary"))
        assert "test-key-very-private" not in row.credential_ciphertext
        assert decrypt_credential(row.credential_ciphertext, str(path)) == "test-key-very-private"
    assert "test-key-very-private" not in client.get(BASE + "/providers", headers=root).text


def test_provider_url_restrictions(monkeypatch):
    from app.core.errors import APIError

    for kind, url in [
        ("ollama", "http://example.com:11434"),
        ("openai_compatible", "http://127.0.0.1:8080/v1"),
        ("openai_compatible", "https://evil.example/v1"),
        ("lm_studio", "http://169.254.1.1:1234/v1"),
    ]:
        try:
            validate_base_url(kind, url)
        except APIError:
            pass
        else:
            raise AssertionError(f"Unsafe URL accepted: {kind}")
    monkeypatch.setattr(get_settings(), "ai_local_hosts", ["192.168.1.10"])
    assert validate_base_url("ollama", "http://192.168.1.10:11434")


def test_master_key_rotation_is_atomic_and_versioned(api, tmp_path, monkeypatch):
    from app import ai_key_rotation
    from app.services.ai.providers import encrypt_credential

    _client, engine, (org, _), _ = api
    old = tmp_path / "old.key"
    new = tmp_path / "new.key"
    old.write_bytes(Fernet.generate_key())
    new.write_bytes(Fernet.generate_key())
    monkeypatch.setattr(get_settings(), "ai_key_file", str(old))
    monkeypatch.setattr(ai_key_rotation, "engine", engine)
    with Session(engine) as db:
        db.add(
            AIProvider(
                code="rotation",
                name="Rotation",
                kind="openai",
                model_id="fixture",
                credential_ciphertext=encrypt_credential("private", str(old)),
                credential_key_version=1,
                allowed_tasks=[],
                enabled=False,
            )
        )
        db.commit()
    assert ai_key_rotation.rotate(str(new)) == 1
    with Session(engine) as db:
        row = db.scalar(select(AIProvider).where(AIProvider.code == "rotation"))
        assert row.credential_key_version == 1
        assert decrypt_credential(row.credential_ciphertext, str(old)) == "private"
    assert ai_key_rotation.rotate(str(new), apply=True) == 1
    with Session(engine) as db:
        row = db.scalar(select(AIProvider).where(AIProvider.code == "rotation"))
        assert row.credential_key_version == 2
        assert decrypt_credential(row.credential_ciphertext, str(new)) == "private"
