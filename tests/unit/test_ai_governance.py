from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.app.ai.domain import estimate_cost, normalize_usage
from backend.app.ai.governance import (
    AIGovernanceLimits,
    AIUsageSnapshot,
    governance_block_reason,
    pricing_is_complete,
    worst_case_cost,
)


def _snapshot(**overrides: object) -> AIUsageSnapshot:
    values: dict[str, object] = {
        "input_tokens": 100,
        "output_tokens": 50,
        "known_cost": Decimal("0.10"),
        "unknown_cost_attempts": 0,
        "consecutive_failures": 0,
        "last_failure_at": None,
    }
    values.update(overrides)
    return AIUsageSnapshot(**values)  # type: ignore[arg-type]


def test_usage_normalization_keeps_unknown_fields_unknown() -> None:
    assert normalize_usage({"prompt_tokens": 4, "completion_tokens": 2}) == {
        "input_tokens": 4,
        "output_tokens": 2,
        "total_tokens": 6,
        "cached_tokens": None,
        "reasoning_tokens": None,
    }


def test_pricing_and_cost_are_exact_or_honestly_unknown() -> None:
    pricing = {"input_cost_per_token": "0.001", "output_cost_per_token": "0.002"}
    assert pricing_is_complete(pricing)
    assert worst_case_cost(100, pricing) == Decimal("0.200")
    assert estimate_cost({"input_tokens": 10, "output_tokens": 5}, pricing) == "0.020"
    assert not pricing_is_complete({})
    assert worst_case_cost(100, {}) is None


def test_budget_and_circuit_limits_fail_closed() -> None:
    limits = AIGovernanceLimits(
        monthly_token_budget=200,
        monthly_cost_budget=Decimal("1.00"),
        circuit_failure_threshold=3,
        circuit_cooldown_seconds=300,
    )
    now = datetime.now(UTC)
    assert (
        governance_block_reason(
            _snapshot(),
            limits,
            reserved_tokens=40,
            reserved_cost=Decimal("0.20"),
            now=now,
        )
        is None
    )
    assert "token budget" in (
        governance_block_reason(
            _snapshot(input_tokens=180, output_tokens=10),
            limits,
            reserved_tokens=20,
            reserved_cost=Decimal("0.01"),
            now=now,
        )
        or ""
    )
    assert "circuit" in (
        governance_block_reason(
            _snapshot(
                consecutive_failures=3,
                last_failure_at=now - timedelta(seconds=10),
            ),
            limits,
            reserved_tokens=1,
            reserved_cost=Decimal("0.01"),
            now=now,
        )
        or ""
    )
