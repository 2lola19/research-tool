from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class AIUsageSnapshot:
    input_tokens: int
    output_tokens: int
    known_cost: Decimal
    unknown_cost_attempts: int
    consecutive_failures: int
    last_failure_at: datetime | None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class AIGovernanceLimits:
    monthly_token_budget: int | None
    monthly_cost_budget: Decimal | None
    circuit_failure_threshold: int
    circuit_cooldown_seconds: int
    allow_unknown_cost: bool = False


def pricing_is_complete(pricing: dict[str, object]) -> bool:
    input_price = pricing.get("input_cost_per_token")
    output_price = pricing.get("output_cost_per_token")
    if input_price is None or output_price is None:
        return False
    try:
        parsed = (Decimal(str(input_price)), Decimal(str(output_price)))
    except Exception:
        return False
    return all(value >= 0 for value in parsed)


def worst_case_cost(token_ceiling: int | None, pricing: dict[str, object]) -> Decimal | None:
    if token_ceiling is None or not pricing_is_complete(pricing):
        return None
    try:
        input_price = Decimal(str(pricing["input_cost_per_token"]))
        output_price = Decimal(str(pricing["output_cost_per_token"]))
    except Exception:
        return None
    return Decimal(token_ceiling) * max(input_price, output_price)


def governance_block_reason(
    snapshot: AIUsageSnapshot,
    limits: AIGovernanceLimits,
    *,
    reserved_tokens: int,
    reserved_cost: Decimal | None,
    now: datetime,
) -> str | None:
    if limits.monthly_token_budget is not None and (
        snapshot.total_tokens + reserved_tokens > limits.monthly_token_budget
    ):
        return "AI monthly token budget would be exceeded"
    if limits.monthly_cost_budget is not None:
        if snapshot.unknown_cost_attempts and not limits.allow_unknown_cost:
            return "AI cost budget cannot be evaluated because prior cost is unknown"
        if reserved_cost is None and not limits.allow_unknown_cost:
            return "AI cost budget requires versioned provider pricing"
        if (
            reserved_cost is not None
            and snapshot.known_cost + reserved_cost > limits.monthly_cost_budget
        ):
            return "AI monthly cost budget would be exceeded"
    if (
        snapshot.last_failure_at is not None
        and snapshot.consecutive_failures >= limits.circuit_failure_threshold
        and (now - snapshot.last_failure_at).total_seconds() < limits.circuit_cooldown_seconds
    ):
        return "AI provider circuit is open after repeated failures"
    return None
