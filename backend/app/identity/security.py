from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

from backend.app.core.errors import AuthenticationError
from backend.app.identity.domain import AuthenticatedIdentity


def _encode_base64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_base64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


class ScryptPasswordHasher:
    algorithm = "scrypt"
    n = 2**14
    r = 8
    p = 1
    salt_bytes = 16
    key_bytes = 32

    def hash_password(self, password: str) -> str:
        if len(password) < 12:
            raise ValueError("password must contain at least 12 characters")
        salt = secrets.token_bytes(self.salt_bytes)
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=self.n,
            r=self.r,
            p=self.p,
            dklen=self.key_bytes,
        )
        return "$".join(
            (
                self.algorithm,
                str(self.n),
                str(self.r),
                str(self.p),
                _encode_base64(salt),
                _encode_base64(digest),
            )
        )

    def verify_password(self, password: str, encoded_hash: str) -> bool:
        try:
            algorithm, n, r, p, salt, expected = encoded_hash.split("$")
            if algorithm != self.algorithm:
                return False
            digest = hashlib.scrypt(
                password.encode("utf-8"),
                salt=_decode_base64(salt),
                n=int(n),
                r=int(r),
                p=int(p),
                dklen=self.key_bytes,
            )
            return hmac.compare_digest(digest, _decode_base64(expected))
        except (ValueError, TypeError):
            return False


class LocalTokenAuthenticationProvider:
    version = "v1"

    def __init__(
        self,
        secret: str,
        token_ttl_seconds: int,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if len(secret) < 24:
            raise ValueError("local authentication secret must contain at least 24 characters")
        self._secret = secret.encode("utf-8")
        self._token_ttl_seconds = token_ttl_seconds
        self._clock = clock

    def issue_token(self, user_id: UUID) -> str:
        issued_at = int(self._clock())
        payload = {
            "exp": issued_at + self._token_ttl_seconds,
            "iat": issued_at,
            "jti": str(uuid4()),
            "sub": str(user_id),
        }
        encoded_payload = _encode_base64(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        unsigned = f"{self.version}.{encoded_payload}"
        signature = _encode_base64(hmac.digest(self._secret, unsigned.encode("ascii"), "sha256"))
        return f"{unsigned}.{signature}"

    def authenticate(self, token: str) -> AuthenticatedIdentity:
        try:
            version, encoded_payload, signature = token.split(".")
            unsigned = f"{version}.{encoded_payload}"
            expected_signature = hmac.digest(
                self._secret,
                unsigned.encode("ascii"),
                "sha256",
            )
            if version != self.version or not hmac.compare_digest(
                expected_signature,
                _decode_base64(signature),
            ):
                raise ValueError
            payload: dict[str, Any] = json.loads(_decode_base64(encoded_payload))
            now = int(self._clock())
            issued_at = int(payload["iat"])
            expires_at = int(payload["exp"])
            if issued_at > now + 60 or expires_at <= now or expires_at <= issued_at:
                raise ValueError
            return AuthenticatedIdentity(user_id=UUID(str(payload["sub"])))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise AuthenticationError("authentication credentials are invalid or expired") from None
