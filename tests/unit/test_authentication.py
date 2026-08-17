from uuid import uuid4

import pytest

from backend.app.core.config import Settings
from backend.app.core.errors import AuthenticationError
from backend.app.identity.security import (
    LocalTokenAuthenticationProvider,
    ScryptPasswordHasher,
    _decode_base64,
    _encode_base64,
)


def test_scrypt_password_hash_round_trip() -> None:
    hasher = ScryptPasswordHasher()
    encoded = hasher.hash_password("correct horse battery staple")

    assert encoded.startswith("scrypt$")
    assert "correct horse battery staple" not in encoded
    assert hasher.verify_password("correct horse battery staple", encoded)
    assert not hasher.verify_password("incorrect password", encoded)
    assert not hasher.verify_password("correct horse battery staple", "invalid")


def test_scrypt_rejects_short_passwords() -> None:
    with pytest.raises(ValueError, match="at least 12"):
        ScryptPasswordHasher().hash_password("too-short")


def test_local_token_is_signed_and_expires() -> None:
    now = [1_000.0]
    provider = LocalTokenAuthenticationProvider(
        "test-local-authentication-secret",
        token_ttl_seconds=60,
        clock=lambda: now[0],
    )
    user_id = uuid4()
    token = provider.issue_token(user_id)

    assert provider.authenticate(token).user_id == user_id

    now[0] = 1_061.0
    with pytest.raises(AuthenticationError):
        provider.authenticate(token)


def test_local_token_rejects_tampering() -> None:
    provider = LocalTokenAuthenticationProvider(
        "test-local-authentication-secret",
        token_ttl_seconds=60,
    )
    token = provider.issue_token(uuid4())
    version, encoded_payload, encoded_signature = token.split(".")
    original_signature = _decode_base64(encoded_signature)
    tampered_signature = bytearray(original_signature)
    tampered_signature[0] ^= 0x01
    tampered_signature_segment = _encode_base64(bytes(tampered_signature))
    tampered = f"{version}.{encoded_payload}.{tampered_signature_segment}"

    assert tampered != token
    assert original_signature != _decode_base64(tampered_signature_segment)

    with pytest.raises(AuthenticationError):
        provider.authenticate(tampered)


def test_local_authentication_is_not_available_in_production() -> None:
    with pytest.raises(ValueError, match="restricted to development and test"):
        Settings(app_env="production")
