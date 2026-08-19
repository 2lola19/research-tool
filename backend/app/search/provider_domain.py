from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID


class ProviderFailureClass(StrEnum):
    TRANSIENT = "TRANSIENT"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    PERMANENT = "PERMANENT"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    BLOCKED = "BLOCKED"

    @property
    def retryable(self) -> bool:
        return self in {
            ProviderFailureClass.TRANSIENT,
            ProviderFailureClass.RATE_LIMITED,
            ProviderFailureClass.TIMEOUT,
        }


class SearchProviderError(Exception):
    """Safe, provider-neutral failure details for one bounded provider run."""

    def __init__(
        self,
        message: str,
        *,
        failure_class: ProviderFailureClass,
        status_code: int | None = None,
        retry_after_seconds: float | None = None,
        response_byte_size: int = 0,
        response_sha256: str | None = None,
        attempts: tuple[ProviderAttemptSnapshot, ...] = (),
    ) -> None:
        super().__init__(message)
        self.message = message
        self.failure_class = failure_class
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.response_byte_size = response_byte_size
        self.response_sha256 = response_sha256
        self.attempts = attempts

    def with_attempts(self, attempts: tuple[ProviderAttemptSnapshot, ...]) -> SearchProviderError:
        return SearchProviderError(
            self.message,
            failure_class=self.failure_class,
            status_code=self.status_code,
            retry_after_seconds=self.retry_after_seconds,
            response_byte_size=self.response_byte_size,
            response_sha256=self.response_sha256,
            attempts=attempts,
        )


@dataclass(frozen=True, slots=True)
class SearchProviderCapability:
    key: str
    display_name: str
    version: str
    base_url: str
    allowed_hosts: frozenset[str]
    supports_pagination: bool
    max_page_size: int
    requires_api_key: bool
    default_media_type: str


@dataclass(frozen=True, slots=True)
class ProviderAttemptSnapshot:
    provider_key: str
    provider_version: str
    page_number: int
    attempt_number: int
    request_fingerprint: str
    started_at: datetime
    completed_at: datetime
    http_status: int | None
    failure_class: ProviderFailureClass | None
    response_byte_size: int
    response_sha256: str | None
    note: str | None

    @staticmethod
    def request_hash(url: str, params: dict[str, str]) -> str:
        canonical = "&".join(f"{key}={params[key]}" for key in sorted(params))
        return hashlib.sha256(f"{url}?{canonical}".encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class SearchProviderAttempt:
    id: UUID
    organization_id: UUID
    review_id: UUID
    search_execution_id: UUID
    provider_key: str
    provider_version: str
    page_number: int
    attempt_number: int
    request_fingerprint: str
    started_at: datetime
    completed_at: datetime
    http_status: int | None
    failure_class: ProviderFailureClass | None
    response_byte_size: int
    response_sha256: str | None
    note: str | None
    created_by_user_id: UUID
    created_at: datetime


def utc_now() -> datetime:
    return datetime.now(UTC)
