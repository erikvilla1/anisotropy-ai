"""Tokens as Cloudflare Access signs them, for the tests: one RSA key pair made per test session, and the claims the application
token carries (its `aud` is a list, as Access writes it). `key_for` stands in for the team's published keys."""

import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

TEAM = "team.cloudflareaccess.com"
AUDIENCE = "a1b2c3d4e5f60718" * 4
ISSUER = f"https://{TEAM}"
KID = "key-1"
EMAIL = "engineer@example.com"


def _pem(key) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


_TEAM_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_PEM = _pem(_TEAM_KEY)
OTHER_PRIVATE_PEM = _pem(_OTHER_KEY)  # a key the team never published
PUBLIC_KEY = _TEAM_KEY.public_key()


def claims(**overrides) -> dict:
    now = int(time.time())
    base = {"aud": [AUDIENCE], "email": EMAIL, "exp": now + 300, "iat": now, "nbf": now, "iss": ISSUER, "type": "app",
            "identity_nonce": "nonce", "sub": "user-1", "country": "US"}
    return {**base, **overrides}


def token(private_pem: bytes = PRIVATE_PEM, **overrides) -> str:
    return jwt.encode(claims(**overrides), private_pem, algorithm="RS256", headers={"kid": KID})


def service_token() -> str:
    """What a service token's request carries: no email, the client id as `common_name`, an empty subject."""
    now = int(time.time())
    return jwt.encode({"type": "app", "aud": [AUDIENCE], "exp": now + 300, "iss": ISSUER, "common_name": "client-id", "iat": now, "sub": ""},
                      PRIVATE_PEM, algorithm="RS256", headers={"kid": KID})


def key_for(_token: str):
    return PUBLIC_KEY
