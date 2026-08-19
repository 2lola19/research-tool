from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace
from ipaddress import ip_address
from urllib.parse import urlsplit

import httpx

from backend.app.search.provider_domain import (
    ProviderAttemptSnapshot,
    ProviderFailureClass,
    SearchProviderError,
    utc_now,
)


@dataclass(frozen=True, slots=True)
class SearchHttpResponse:
    status_code: int
    headers: Mapping[str, str]
    content: bytes


class SearchHttpTransport:
    async def get(
        self,
        *,
        url: str,
        params: dict[str, str],
        headers: dict[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> SearchHttpResponse:
        raise NotImplementedError


class HttpxSearchHttpTransport(SearchHttpTransport):
    """Small infrastructure adapter; provider code depends only on SearchHttpTransport."""

    async def get(
        self,
        *,
        url: str,
        params: dict[str, str],
        headers: dict[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> SearchHttpResponse:
        try:
            async with (
                httpx.AsyncClient(
                    follow_redirects=False,
                    timeout=httpx.Timeout(timeout_seconds),
                ) as client,
                client.stream("GET", url, params=params, headers=headers) as response,
            ):
                declared_size = response.headers.get("content-length")
                if declared_size is not None:
                    try:
                        if int(declared_size) > max_response_bytes:
                            raise SearchProviderError(
                                "provider response exceeds the configured size limit",
                                failure_class=ProviderFailureClass.BLOCKED,
                                status_code=response.status_code,
                            )
                    except ValueError:
                        pass
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > max_response_bytes:
                        raise SearchProviderError(
                            "provider response exceeds the configured size limit",
                            failure_class=ProviderFailureClass.BLOCKED,
                            status_code=response.status_code,
                            response_byte_size=total,
                        )
                    chunks.append(chunk)
                return SearchHttpResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    content=b"".join(chunks),
                )
        except SearchProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise SearchProviderError(
                "scholarly provider request timed out",
                failure_class=ProviderFailureClass.TIMEOUT,
            ) from exc
        except httpx.RequestError as exc:
            raise SearchProviderError(
                "scholarly provider request failed",
                failure_class=ProviderFailureClass.TRANSIENT,
            ) from exc


def validate_provider_url(url: str, allowed_hosts: frozenset[str]) -> None:
    parsed = urlsplit(url)
    host = parsed.hostname.casefold() if parsed.hostname else ""
    if (
        parsed.scheme.casefold() != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or (parsed.port is not None and parsed.port != 443)
        or host not in allowed_hosts
    ):
        raise SearchProviderError(
            "provider URL is outside the configured HTTPS host allowlist",
            failure_class=ProviderFailureClass.BLOCKED,
        )
    try:
        address = ip_address(host)
    except ValueError:
        return
    if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
        raise SearchProviderError(
            "provider URL resolves to a non-public address",
            failure_class=ProviderFailureClass.BLOCKED,
        )


def build_polite_user_agent(application: str, contact_email: str | None) -> str:
    cleaned_application = " ".join(application.split())
    if not cleaned_application or any(char in cleaned_application for char in "\r\n"):
        raise ValueError("provider user-agent application is invalid")
    if contact_email is None:
        return cleaned_application
    cleaned_email = contact_email.strip()
    if (
        not cleaned_email
        or "@" not in cleaned_email
        or any(char in cleaned_email for char in "\r\n")
    ):
        raise ValueError("provider contact email is invalid")
    return f"{cleaned_application} (+mailto:{cleaned_email})"


SleepFunction = Callable[[float], Awaitable[None]]


class ProviderHttpClient:
    def __init__(
        self,
        *,
        provider_key: str,
        provider_version: str,
        allowed_hosts: frozenset[str],
        transport: SearchHttpTransport,
        user_agent: str,
        timeout_seconds: float,
        max_response_bytes: int,
        max_attempts: int = 3,
        backoff_base_seconds: float = 0.25,
        backoff_cap_seconds: float = 4.0,
        min_interval_seconds: float = 0.0,
        sleep: SleepFunction = asyncio.sleep,
        sensitive_param_keys: frozenset[str] = frozenset(),
    ) -> None:
        if max_attempts < 1 or max_attempts > 5:
            raise ValueError("provider attempts must be between 1 and 5")
        if timeout_seconds <= 0 or max_response_bytes <= 0:
            raise ValueError("provider timeout and response limit must be positive")
        self.provider_key = provider_key
        self.provider_version = provider_version
        self.allowed_hosts = allowed_hosts
        self.transport = transport
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.max_attempts = max_attempts
        self.backoff_base_seconds = backoff_base_seconds
        self.backoff_cap_seconds = backoff_cap_seconds
        self.min_interval_seconds = min_interval_seconds
        self.sleep = sleep
        self.sensitive_param_keys = {key.casefold() for key in sensitive_param_keys}
        self.attempts: list[ProviderAttemptSnapshot] = []
        self._last_request_at: float | None = None

    async def get(
        self,
        *,
        url: str,
        params: dict[str, str],
        page_number: int,
    ) -> SearchHttpResponse:
        validate_provider_url(url, self.allowed_hosts)
        safe_params = {
            key: value
            for key, value in params.items()
            if key.casefold() not in self.sensitive_param_keys
        }
        request_fingerprint = ProviderAttemptSnapshot.request_hash(url, safe_params)
        for attempt_number in range(1, self.max_attempts + 1):
            await self._wait_for_rate_limit()
            started_at = utc_now()
            try:
                response = await self.transport.get(
                    url=url,
                    params=params,
                    headers={
                        "Accept": "application/json, application/xml, text/xml;q=0.9",
                        "User-Agent": self.user_agent,
                    },
                    timeout_seconds=self.timeout_seconds,
                    max_response_bytes=self.max_response_bytes,
                )
                if 300 <= response.status_code < 400:
                    raise SearchProviderError(
                        "provider redirects are not followed",
                        failure_class=ProviderFailureClass.BLOCKED,
                        status_code=response.status_code,
                        response_byte_size=len(response.content),
                        response_sha256=hashlib.sha256(response.content).hexdigest(),
                    )
                if response.status_code >= 400:
                    raise self._http_error(response)
                self.attempts.append(
                    ProviderAttemptSnapshot(
                        provider_key=self.provider_key,
                        provider_version=self.provider_version,
                        page_number=page_number,
                        attempt_number=attempt_number,
                        request_fingerprint=request_fingerprint,
                        started_at=started_at,
                        completed_at=utc_now(),
                        http_status=response.status_code,
                        failure_class=None,
                        response_byte_size=len(response.content),
                        response_sha256=hashlib.sha256(response.content).hexdigest(),
                        note=None,
                    )
                )
                return response
            except SearchProviderError as exc:
                self.attempts.append(
                    ProviderAttemptSnapshot(
                        provider_key=self.provider_key,
                        provider_version=self.provider_version,
                        page_number=page_number,
                        attempt_number=attempt_number,
                        request_fingerprint=request_fingerprint,
                        started_at=started_at,
                        completed_at=utc_now(),
                        http_status=exc.status_code,
                        failure_class=exc.failure_class,
                        response_byte_size=exc.response_byte_size,
                        response_sha256=exc.response_sha256,
                        note=exc.message,
                    )
                )
                if not exc.failure_class.retryable or attempt_number >= self.max_attempts:
                    raise exc.with_attempts(tuple(self.attempts)) from exc
                delay = (
                    exc.retry_after_seconds
                    if exc.retry_after_seconds is not None
                    else min(
                        self.backoff_cap_seconds,
                        self.backoff_base_seconds * (2 ** (attempt_number - 1)),
                    )
                )
                await self.sleep(max(0.0, min(delay, self.backoff_cap_seconds)))
        raise AssertionError("provider retry loop exhausted without a result")

    def invalid_response(self, *, page_number: int, message: str) -> SearchProviderError:
        for index in range(len(self.attempts) - 1, -1, -1):
            attempt = self.attempts[index]
            if attempt.page_number == page_number and attempt.failure_class is None:
                self.attempts[index] = replace(
                    attempt,
                    failure_class=ProviderFailureClass.INVALID_RESPONSE,
                    note=message,
                )
                break
        return SearchProviderError(
            message,
            failure_class=ProviderFailureClass.INVALID_RESPONSE,
            attempts=tuple(self.attempts),
        )

    async def _wait_for_rate_limit(self) -> None:
        if self._last_request_at is not None and self.min_interval_seconds > 0:
            loop_time = asyncio.get_running_loop().time()
            remaining = self.min_interval_seconds - (loop_time - self._last_request_at)
            if remaining > 0:
                await self.sleep(remaining)
        self._last_request_at = asyncio.get_running_loop().time()

    @staticmethod
    def _http_error(response: SearchHttpResponse) -> SearchProviderError:
        status_code = response.status_code
        if status_code == 429:
            failure_class = ProviderFailureClass.RATE_LIMITED
        elif status_code in {408, 425} or status_code >= 500:
            failure_class = ProviderFailureClass.TRANSIENT
        else:
            failure_class = ProviderFailureClass.PERMANENT
        retry_after: float | None = None
        raw_retry_after = response.headers.get("retry-after")
        if raw_retry_after is not None:
            try:
                retry_after = float(raw_retry_after)
            except ValueError:
                retry_after = None
        return SearchProviderError(
            f"provider returned HTTP {status_code}",
            failure_class=failure_class,
            status_code=status_code,
            retry_after_seconds=retry_after,
            response_byte_size=len(response.content),
            response_sha256=hashlib.sha256(response.content).hexdigest(),
        )
