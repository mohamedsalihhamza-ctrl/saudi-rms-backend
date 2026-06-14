import httpx
from jose import jwk, jwt, JWTError
from jose.constants import Algorithms
from dataclasses import dataclass
from typing import Any


GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"

_jwks_cache: dict[str, list[dict[str, Any]]] = {}
_google_client_id: str | None = None
_apple_client_id: str | None = None


def configure_sso(google_client_id: str | None = None, apple_client_id: str | None = None):
    global _google_client_id, _apple_client_id
    _google_client_id = google_client_id
    _apple_client_id = apple_client_id


def is_google_sso_enabled() -> bool:
    return bool(_google_client_id)


def is_apple_sso_enabled() -> bool:
    return bool(_apple_client_id)


async def _fetch_jwks(url: str) -> list[dict[str, Any]]:
    if url in _jwks_cache:
        return _jwks_cache[url]
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        keys = data.get("keys", [])
        _jwks_cache[url] = keys
        return keys


def _find_key(jwks: list[dict[str, Any]], header: dict[str, Any]) -> dict[str, Any] | None:
    kid = header.get("kid")
    if kid:
        for key in jwks:
            if key.get("kid") == kid:
                return key
    return None


@dataclass
class SSOUserInfo:
    provider: str
    sub: str
    email: str
    name: str
    email_verified: bool = False


async def verify_google_token(id_token: str) -> SSOUserInfo:
    if not _google_client_id:
        raise ValueError("Google SSO is not configured")

    unverified_header = jwt.get_unverified_header(id_token)
    jwks = await _fetch_jwks(GOOGLE_JWKS_URL)
    signing_key = _find_key(jwks, unverified_header)

    if not signing_key:
        raise ValueError("No matching Google signing key found")

    public_key = jwk.construct(signing_key)
    try:
        payload = jwt.decode(
            id_token,
            public_key,
            algorithms=[Algorithms.RS256],
            audience=_google_client_id,
            issuer="https://accounts.google.com",
        )
    except JWTError as e:
        raise ValueError(f"Invalid Google token: {e}")

    email = payload.get("email", "")
    return SSOUserInfo(
        provider="google",
        sub=payload["sub"],
        email=email,
        name=payload.get("name", email.split("@")[0] if email else ""),
        email_verified=payload.get("email_verified", False),
    )


async def verify_apple_token(id_token: str) -> SSOUserInfo:
    if not _apple_client_id:
        raise ValueError("Apple SSO is not configured")

    unverified_header = jwt.get_unverified_header(id_token)
    jwks = await _fetch_jwks(APPLE_JWKS_URL)
    signing_key = _find_key(jwks, unverified_header)

    if not signing_key:
        raise ValueError("No matching Apple signing key found")

    public_key = jwk.construct(signing_key)
    try:
        payload = jwt.decode(
            id_token,
            public_key,
            algorithms=[Algorithms.RS256],
            audience=_apple_client_id,
            issuer="https://appleid.apple.com",
        )
    except JWTError as e:
        raise ValueError(f"Invalid Apple token: {e}")

    email = payload.get("email", "")
    return SSOUserInfo(
        provider="apple",
        sub=payload["sub"],
        email=email,
        name=payload.get("name", email.split("@")[0] if email else ""),
        email_verified=True,
    )
