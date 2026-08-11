from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, cast
from uuid import UUID


class InstrumentDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AssessmentStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"


class ComparisonStatus(StrEnum):
    AGREEMENT = "AGREEMENT"
    CONFLICT = "CONFLICT"
    ADJUDICATED = "ADJUDICATED"


@dataclass(frozen=True, slots=True)
class RiskOfBiasInstrument:
    id: UUID
    organization_id: UUID
    review_id: UUID
    key: str
    name: str
    description: str | None
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RiskOfBiasInstrumentVersion:
    id: UUID
    instrument_id: UUID
    organization_id: UUID
    review_id: UUID
    version: int
    definition: dict[str, Any]
    content_hash: str
    created_by_user_id: UUID
    created_at: datetime
    decision: InstrumentDecision | None


@dataclass(frozen=True, slots=True)
class RiskOfBiasAnswer:
    id: UUID
    assessment_id: UUID
    question_key: str
    answer: str
    rationale: str | None
    evidence_location_id: UUID | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class RiskOfBiasDomainJudgment:
    id: UUID
    assessment_id: UUID
    domain_key: str
    suggested_judgment: str | None
    final_judgment: str
    rationale: str
    override_reason: str | None
    evidence_location_id: UUID | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class RiskOfBiasAssessment:
    id: UUID
    organization_id: UUID
    review_id: UUID
    study_id: UUID
    instrument_version_id: UUID
    assessor_user_id: UUID
    round_number: int
    revision: int
    supersedes_assessment_id: UUID | None
    status: AssessmentStatus
    overall_suggested_judgment: str | None
    overall_final_judgment: str | None
    overall_rationale: str | None
    overall_override_reason: str | None
    overall_evidence_location_id: UUID | None
    created_at: datetime
    submitted_at: datetime | None
    answers: tuple[RiskOfBiasAnswer, ...]
    domain_judgments: tuple[RiskOfBiasDomainJudgment, ...]


@dataclass(frozen=True, slots=True)
class RiskOfBiasComparison:
    id: UUID
    organization_id: UUID
    review_id: UUID
    study_id: UUID
    instrument_version_id: UUID
    round_number: int
    assessment_a_id: UUID
    assessment_b_id: UUID
    status: ComparisonStatus
    differences: tuple[dict[str, Any], ...]
    compared_by_user_id: UUID
    compared_at: datetime
    adjudicated_snapshot: dict[str, Any] | None
    adjudicated_by_user_id: UUID | None
    adjudication_reason: str | None
    adjudication_evidence_location_id: UUID | None
    adjudicated_at: datetime | None


def normalize_instrument_definition(definition: dict[str, Any]) -> dict[str, Any]:
    designs = _unique_values(definition.get("applicable_study_designs"), "study designs")
    answers = _choices(definition.get("answer_choices"), "answer choices")
    domain_choices = _choices(definition.get("domain_judgment_choices"), "domain judgment choices")
    overall_choices = _choices(
        definition.get("overall_judgment_choices"), "overall judgment choices"
    )
    answer_values = {item["value"] for item in answers}
    domain_values = {item["value"] for item in domain_choices}
    overall_values = {item["value"] for item in overall_choices}
    raw_domains = definition.get("domains")
    if not isinstance(raw_domains, list) or not raw_domains:
        raise ValueError("instrument requires ordered domains")
    domains: list[dict[str, Any]] = []
    domain_keys: set[str] = set()
    question_keys: set[str] = set()
    for domain_order, raw_domain in enumerate(raw_domains):
        if not isinstance(raw_domain, dict):
            raise ValueError("instrument domains must be objects")
        domain_key = _key(raw_domain.get("key"), "domain key")
        if domain_key in domain_keys:
            raise ValueError("domain keys must be unique")
        domain_keys.add(domain_key)
        raw_questions = raw_domain.get("questions")
        if not isinstance(raw_questions, list) or not raw_questions:
            raise ValueError(f"domain {domain_key} requires signalling questions")
        questions: list[dict[str, Any]] = []
        for question_order, raw_question in enumerate(raw_questions):
            if not isinstance(raw_question, dict):
                raise ValueError("signalling questions must be objects")
            question_key = _key(raw_question.get("key"), "question key")
            if question_key in question_keys:
                raise ValueError("question keys must be globally unique")
            question_keys.add(question_key)
            allowed = raw_question.get("allowed_answers", sorted(answer_values))
            if not isinstance(allowed, list) or not allowed or not set(allowed) <= answer_values:
                raise ValueError(f"question {question_key} has invalid answer choices")
            questions.append(
                {
                    "key": question_key,
                    "text": _text(raw_question.get("text"), "question text"),
                    "guidance": _optional_text(raw_question.get("guidance")),
                    "required": bool(raw_question.get("required", True)),
                    "allowed_answers": list(dict.fromkeys(str(item) for item in allowed)),
                    "order": question_order,
                }
            )
        rule = _domain_rule(raw_domain.get("rule"), answer_values, domain_values)
        domains.append(
            {
                "key": domain_key,
                "label": _text(raw_domain.get("label"), "domain label"),
                "guidance": _optional_text(raw_domain.get("guidance")),
                "questions": questions,
                "rule": rule,
                "order": domain_order,
            }
        )
    overall_rule = _overall_rule(definition.get("overall_rule"), domain_values, overall_values)
    return {
        "name": _text(definition.get("name"), "instrument name"),
        "version_label": _text(definition.get("version_label"), "version label"),
        "guidance": _optional_text(definition.get("guidance")),
        "applicable_study_designs": designs,
        "answer_choices": answers,
        "domain_judgment_choices": domain_choices,
        "overall_judgment_choices": overall_choices,
        "domains": domains,
        "overall_rule": overall_rule,
    }


def suggest_domain_judgment(
    definition: dict[str, Any], domain_key: str, answers: dict[str, str]
) -> str | None:
    domain = next((item for item in definition["domains"] if item["key"] == domain_key), None)
    if domain is None or domain["rule"] is None:
        return None
    rule = domain["rule"]
    mapped = [rule["answer_mapping"].get(answers.get(item["key"])) for item in domain["questions"]]
    candidates = [item for item in mapped if item is not None]
    if not candidates:
        return cast(str | None, rule.get("default"))
    severity = {value: index for index, value in enumerate(rule["severity_order"])}
    return cast(str, max(candidates, key=lambda value: severity[value]))


def suggest_overall_judgment(
    definition: dict[str, Any], domain_judgments: dict[str, str]
) -> str | None:
    rule = definition.get("overall_rule")
    if rule is None or not domain_judgments:
        return None
    severity = {value: index for index, value in enumerate(rule["severity_order"])}
    worst = max(domain_judgments.values(), key=lambda value: severity[value])
    return cast(str | None, rule["domain_mapping"].get(worst))


def assessment_snapshot(assessment: RiskOfBiasAssessment) -> dict[str, Any]:
    return {
        "answers": {
            item.question_key: {
                "answer": item.answer,
                "rationale": item.rationale,
                "evidence_location_id": (
                    str(item.evidence_location_id) if item.evidence_location_id else None
                ),
            }
            for item in assessment.answers
        },
        "domains": {
            item.domain_key: {
                "suggested_judgment": item.suggested_judgment,
                "final_judgment": item.final_judgment,
                "rationale": item.rationale,
                "override_reason": item.override_reason,
                "evidence_location_id": (
                    str(item.evidence_location_id) if item.evidence_location_id else None
                ),
            }
            for item in assessment.domain_judgments
        },
        "overall": {
            "suggested_judgment": assessment.overall_suggested_judgment,
            "final_judgment": assessment.overall_final_judgment,
            "rationale": assessment.overall_rationale,
            "override_reason": assessment.overall_override_reason,
            "evidence_location_id": (
                str(assessment.overall_evidence_location_id)
                if assessment.overall_evidence_location_id
                else None
            ),
        },
    }


def compare_assessment_snapshots(
    assessment_a: RiskOfBiasAssessment, assessment_b: RiskOfBiasAssessment
) -> tuple[dict[str, Any], ...]:
    differences: list[dict[str, Any]] = []
    answers_a = {item.question_key: item.answer for item in assessment_a.answers}
    answers_b = {item.question_key: item.answer for item in assessment_b.answers}
    for key in sorted(set(answers_a) | set(answers_b)):
        if answers_a.get(key) != answers_b.get(key):
            differences.append(
                {
                    "scope": "answer",
                    "key": key,
                    "value_a": answers_a.get(key),
                    "value_b": answers_b.get(key),
                }
            )
    domains_a = {item.domain_key: item.final_judgment for item in assessment_a.domain_judgments}
    domains_b = {item.domain_key: item.final_judgment for item in assessment_b.domain_judgments}
    for key in sorted(set(domains_a) | set(domains_b)):
        if domains_a.get(key) != domains_b.get(key):
            differences.append(
                {
                    "scope": "domain",
                    "key": key,
                    "value_a": domains_a.get(key),
                    "value_b": domains_b.get(key),
                }
            )
    if assessment_a.overall_final_judgment != assessment_b.overall_final_judgment:
        differences.append(
            {
                "scope": "overall",
                "key": "overall",
                "value_a": assessment_a.overall_final_judgment,
                "value_b": assessment_b.overall_final_judgment,
            }
        )
    return tuple(differences)


def _choices(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"instrument requires {label}")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"{label} must be objects")
        choice = _key(item.get("value"), label)
        if choice in seen:
            raise ValueError(f"{label} must be unique")
        seen.add(choice)
        result.append(
            {
                "value": choice,
                "label": _text(item.get("label"), label),
                "missingness": bool(item.get("missingness", False)),
            }
        )
    return result


def _domain_rule(value: Any, answers: set[str], judgments: set[str]) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or value.get("type") != "ANSWER_SEVERITY":
        raise ValueError("unsupported domain judgment rule")
    mapping = value.get("answer_mapping")
    severity = value.get("severity_order")
    if (
        not isinstance(mapping, dict)
        or not set(mapping) <= answers
        or not set(mapping.values()) <= judgments
    ):
        raise ValueError("domain rule has invalid answer mapping")
    if not isinstance(severity, list) or set(severity) != judgments:
        raise ValueError("domain rule severity must contain every domain judgment")
    default = value.get("default")
    if default is not None and default not in judgments:
        raise ValueError("domain rule default is invalid")
    return {
        "type": "ANSWER_SEVERITY",
        "answer_mapping": dict(sorted(mapping.items())),
        "severity_order": severity,
        "default": default,
    }


def _overall_rule(value: Any, domains: set[str], overall: set[str]) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or value.get("type") != "MAX_DOMAIN_SEVERITY":
        raise ValueError("unsupported overall judgment rule")
    mapping = value.get("domain_mapping")
    severity = value.get("severity_order")
    if (
        not isinstance(mapping, dict)
        or set(mapping) != domains
        or not set(mapping.values()) <= overall
    ):
        raise ValueError("overall rule has invalid domain mapping")
    if not isinstance(severity, list) or set(severity) != domains:
        raise ValueError("overall rule severity must contain every domain judgment")
    return {
        "type": "MAX_DOMAIN_SEVERITY",
        "domain_mapping": dict(sorted(mapping.items())),
        "severity_order": severity,
    }


def _unique_values(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"instrument requires {label}")
    result = [_key(item, label) for item in value]
    if len(result) != len(set(result)):
        raise ValueError(f"{label} must be unique")
    return result


def _key(value: Any, label: str) -> str:
    result = str(value or "").strip().upper()
    if (
        not result
        or len(result) > 120
        or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in result)
    ):
        raise ValueError(f"{label} is invalid")
    return result


def _text(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{label} is required")
    return result


def _optional_text(value: Any) -> str | None:
    result = str(value or "").strip()
    return result or None
