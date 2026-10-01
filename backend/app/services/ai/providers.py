"""Authenticated provider calls; no browser-visible credentials or arbitrary URL fetches."""

import ipaddress
import json
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.errors import APIError

LOCAL_KINDS = {"ollama", "lm_studio"}
TASKS = {"class_recommendation", "practice_generation", "progress_summary"}
DEFAULT_URLS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "claude": "https://api.anthropic.com/v1/messages",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}


def validate_base_url(kind: str, value: str) -> str:
    if kind in DEFAULT_URLS:
        if value:
            raise APIError(422, "AI_URL_FIXED")
        return ""
    parsed = urlsplit(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname:
        raise APIError(422, "AI_URL_INVALID")
    if parsed.path.rstrip("/") not in {"", "/v1"}:
        raise APIError(422, "AI_URL_INVALID")
    if kind in LOCAL_KINDS:
        if parsed.scheme != "http":
            raise APIError(422, "AI_URL_INVALID")
        # IP literals avoid DNS rebinding. Host-gateway names must be handled by a trusted proxy.
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError as error:
            raise APIError(422, "AI_LOCAL_IP_REQUIRED") from error
        if (
            not address.is_private
            or address.is_loopback
            or address.is_link_local
            or parsed.hostname not in get_settings().ai_local_hosts
        ):
            raise APIError(422, "AI_URL_INVALID")
        if kind == "ollama" and parsed.path.rstrip("/"):
            raise APIError(422, "AI_URL_INVALID")
        if kind == "lm_studio" and parsed.path.rstrip("/") != "/v1":
            raise APIError(422, "AI_URL_INVALID")
    elif kind == "openai_compatible":
        if parsed.scheme != "https":
            raise APIError(422, "AI_URL_INVALID")
        if parsed.hostname not in get_settings().ai_custom_hosts:
            raise APIError(422, "AI_URL_NOT_ALLOWED")
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            pass
        else:
            if not address.is_global:
                raise APIError(422, "AI_URL_INVALID")
    else:
        raise APIError(422, "AI_KIND_INVALID")
    return value.rstrip("/")


def _fernet(key_path: str) -> Fernet:
    if not key_path:
        raise APIError(503, "AI_KEY_UNAVAILABLE")
    try:
        key = Path(key_path).read_bytes().strip()
        return Fernet(key)
    except (OSError, ValueError) as error:
        raise APIError(503, "AI_KEY_UNAVAILABLE") from error


def encrypt_credential(value: str, key_path: str) -> str:
    return _fernet(key_path).encrypt(value.encode()).decode()


def decrypt_credential(value: str | None, key_path: str) -> str:
    if not value:
        return ""
    try:
        return _fernet(key_path).decrypt(value.encode()).decode()
    except InvalidToken as error:
        raise APIError(503, "AI_KEY_UNAVAILABLE") from error


def complete(provider, system: str, payload: dict, key_path: str) -> dict:
    """Return a JSON object. Output schema and business semantics are checked by callers."""
    secret = decrypt_credential(provider.credential_ciphertext, key_path)
    user_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    kind = provider.kind
    headers = {"Content-Type": "application/json"}
    if kind == "gemini":
        url = f"{DEFAULT_URLS[kind]}/models/{quote(provider.model_id, safe='')}:generateContent"
        headers["x-goog-api-key"] = secret
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user_text}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": provider.max_output_tokens,
            },
        }
    elif kind == "claude":
        url = DEFAULT_URLS[kind]
        headers.update({"x-api-key": secret, "anthropic-version": "2023-06-01"})
        body = {
            "model": provider.model_id,
            "max_tokens": provider.max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user_text}],
        }
    elif kind == "ollama":
        url = f"{provider.base_url}/api/chat"
        body = {
            "model": provider.model_id,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
        }
        if secret:
            headers["Authorization"] = f"Bearer {secret}"
    else:
        url = (
            DEFAULT_URLS["openai"] if kind == "openai" else f"{provider.base_url}/chat/completions"
        )
        if secret:
            headers["Authorization"] = f"Bearer {secret}"
        body = {
            "model": provider.model_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
            (
                "max_completion_tokens" if kind == "openai" else "max_tokens"
            ): provider.max_output_tokens,
        }
    try:
        with httpx.Client(
            timeout=provider.timeout_seconds, follow_redirects=False, trust_env=False
        ) as client:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            if len(response.content) > 1_000_000:
                raise ValueError("provider response too large")
            data = response.json()
        if kind == "gemini":
            output = data["candidates"][0]["content"]["parts"][0]["text"]
        elif kind == "claude":
            output = data["content"][0]["text"]
        elif kind == "ollama":
            output = data["message"]["content"]
        else:
            output = data["choices"][0]["message"]["content"]
        result = json.loads(output)
        if not isinstance(result, dict):
            raise ValueError("expected object")
        usage = data.get("usageMetadata", {}) if kind == "gemini" else data.get("usage", {})
        tokens = (data.get("eval_count", 0) if kind == "ollama" else
                  usage.get("output_tokens", usage.get("completion_tokens",
                  usage.get("candidatesTokenCount", 0))))
        result["_provider_tokens"] = tokens if isinstance(tokens, int) and tokens >= 0 else 0
        return result
    except (
        httpx.HTTPError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        # Never surface raw provider response: it can contain prompts or credentials.
        raise APIError(503, "AI_PROVIDER_FAILED") from error
