from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from tests.integration.test_tenant_isolation import TenantApi

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def _lead_headers(tenant_api: TenantApi) -> dict[str, str]:
    return tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)


def _create_source(
    tenant_api: TenantApi,
    *,
    key: str = "pubmed",
    classification: str = "BIBLIOGRAPHIC_DATABASE",
) -> dict[str, Any]:
    response = tenant_api.client.post(
        "/api/v1/search-executions/sources",
        headers=_lead_headers(tenant_api),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "source_key": key,
            "display_name": key.replace("-", " ").title(),
            "classification": classification,
            "provider_name": "Fixture Search Provider",
            "platform_name": "Fixture Platform",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_execution(
    tenant_api: TenantApi,
    source_id: str,
    *,
    result_count: int,
    status: str = "COMPLETED",
    exact_query: str | None = "(systematic review[Title])",
    method: str = "FILE_IMPORT",
    strategy_version_id: str | None = None,
    translation_id: str | None = None,
    executed_at: datetime = datetime(2026, 8, 11, 9, 30, tzinfo=UTC),
    supersedes_execution_id: str | None = None,
) -> dict[str, Any]:
    response = tenant_api.client.post(
        "/api/v1/search-executions",
        headers=_lead_headers(tenant_api),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "source_id": source_id,
            "search_strategy_version_id": strategy_version_id,
            "search_translation_id": translation_id,
            "supersedes_execution_id": supersedes_execution_id,
            "method": method,
            "exact_query": exact_query,
            "filters": {"language": "all", "date": "inception-present"},
            "executed_at": executed_at.isoformat(),
            "software_version": "fixture-search-provider/1",
            "status": status,
            "provider_result_count": result_count if status == "COMPLETED" else None,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _record_completed_execution(
    tenant_api: TenantApi,
    *,
    source_key: str = "fixture-database",
    classification: str = "BIBLIOGRAPHIC_DATABASE",
) -> dict[str, Any]:
    batches_response = tenant_api.client.get(
        f"/api/v1/citations/reviews/{tenant_api.ids.assigned_review}/imports",
        headers=_lead_headers(tenant_api),
    )
    assert batches_response.status_code == 200, batches_response.text
    batches = batches_response.json()
    source = _create_source(tenant_api, key=source_key, classification=classification)
    execution = _create_execution(
        tenant_api,
        source["id"],
        result_count=sum(batch["record_count"] for batch in batches),
    )
    for batch in batches:
        linked = tenant_api.client.post(
            f"/api/v1/search-executions/{execution['id']}/imports",
            headers=_lead_headers(tenant_api),
            json={
                "review_id": str(tenant_api.ids.assigned_review),
                "import_batch_id": batch["id"],
            },
        )
        assert linked.status_code == 200, linked.text
    return execution


def test_search_execution_retains_strategy_translation_and_repeated_history(
    tenant_api: TenantApi,
) -> None:
    from tests.integration.test_tenant_isolation import _approved_protocol

    protocol_id = _approved_protocol(
        tenant_api,
        user_id=tenant_api.ids.lead_a,
        review_id=tenant_api.ids.assigned_review,
        suffix="search-execution",
    )
    strategy_response = tenant_api.client.post(
        "/api/v1/search-strategies/versions",
        headers=_lead_headers(tenant_api),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "protocol_version_id": protocol_id,
            "content": {
                "name": "Search provenance fixture",
                "concepts": [{"label": "review", "terms": [{"text": "systematic review"}]}],
            },
        },
    )
    assert strategy_response.status_code == 201, strategy_response.text
    strategy = strategy_response.json()
    translation_response = tenant_api.client.post(
        f"/api/v1/search-strategies/versions/{strategy['id']}/translations",
        headers=_lead_headers(tenant_api),
        json={"provider": "pubmed"},
    )
    assert translation_response.status_code == 201, translation_response.text
    translation = translation_response.json()
    source = _create_source(tenant_api)
    initial = _create_execution(
        tenant_api,
        source["id"],
        result_count=0,
        exact_query=translation["query"],
        method="FIXTURE",
        strategy_version_id=strategy["id"],
        translation_id=translation["id"],
    )
    update = _create_execution(
        tenant_api,
        source["id"],
        result_count=0,
        exact_query=f"{translation['query']} AND 2026[dp]",
        method="FIXTURE",
        strategy_version_id=strategy["id"],
        translation_id=translation["id"],
        executed_at=datetime(2026, 8, 11, 10, 30, tzinfo=UTC),
    )
    listed = tenant_api.client.get(
        f"/api/v1/search-executions/reviews/{tenant_api.ids.assigned_review}",
        headers=_lead_headers(tenant_api),
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [initial["id"], update["id"]]
    assert listed.json()[0]["search_strategy_version_id"] == strategy["id"]
    assert listed.json()[0]["search_translation_id"] == translation["id"]
    assert listed.json()[0]["exact_query"] == translation["query"]

    immutable = tenant_api.client.post(
        f"/api/v1/search-executions/{initial['id']}/events",
        headers=_lead_headers(tenant_api),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "status": "FAILED",
            "note": "must not overwrite a completed execution",
        },
    )
    assert immutable.status_code == 409
    correction = _create_execution(
        tenant_api,
        source["id"],
        result_count=0,
        exact_query=translation["query"],
        method="FIXTURE",
        strategy_version_id=strategy["id"],
        translation_id=translation["id"],
        executed_at=datetime(2026, 8, 11, 11, 30, tzinfo=UTC),
        supersedes_execution_id=initial["id"],
    )
    duplicate_correction = tenant_api.client.post(
        "/api/v1/search-executions",
        headers=_lead_headers(tenant_api),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "source_id": source["id"],
            "supersedes_execution_id": initial["id"],
            "method": "FIXTURE",
            "exact_query": translation["query"],
            "filters": {},
            "executed_at": datetime(2026, 8, 11, 12, 30, tzinfo=UTC).isoformat(),
            "status": "COMPLETED",
            "provider_result_count": 0,
        },
    )
    assert correction["supersedes_execution_id"] == initial["id"]
    assert duplicate_correction.status_code == 409


def test_search_execution_linkage_prisma_groups_and_precise_blockers(
    tenant_api: TenantApi,
) -> None:
    import_response = tenant_api.client.post(
        "/api/v1/citations/imports",
        headers=_lead_headers(tenant_api),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "source_format": "RIS",
            "source_name": "reference-list.ris",
            "content": "TY  - JOUR\nTI  - Discovery path\nER  -\n",
        },
    )
    assert import_response.status_code == 201, import_response.text
    batch = import_response.json()
    source = _create_source(tenant_api, key="reference-list", classification="REFERENCE_LIST")
    partial = _create_execution(
        tenant_api, source["id"], result_count=1, status="PARTIAL", exact_query=None
    )
    failed = _create_execution(
        tenant_api, source["id"], result_count=1, status="FAILED", exact_query=None
    )
    blocked = tenant_api.client.get(
        f"/api/v1/prisma/reviews/{tenant_api.ids.assigned_review}/summary",
        headers=_lead_headers(tenant_api),
    )
    codes = {item["code"] for item in blocked.json()["readiness"]["blockers"]}
    assert {
        "NO_COMPLETED_SEARCH_EXECUTION",
        "SEARCH_EXECUTION_PARTIAL",
        "SEARCH_EXECUTION_FAILED",
    } <= codes

    completed = _create_execution(tenant_api, source["id"], result_count=1, exact_query=None)
    linked = tenant_api.client.post(
        f"/api/v1/search-executions/{completed['id']}/imports",
        headers=_lead_headers(tenant_api),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "import_batch_id": batch["id"],
        },
    )
    assert linked.json() == {"linked_record_count": 1}
    second_source = _create_source(
        tenant_api, key="citation-searching", classification="CITATION_SEARCHING"
    )
    second_execution = _create_execution(
        tenant_api, second_source["id"], result_count=1, exact_query=None
    )
    second_link = tenant_api.client.post(
        f"/api/v1/search-executions/{second_execution['id']}/imports",
        headers=_lead_headers(tenant_api),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "import_batch_id": batch["id"],
        },
    )
    assert second_link.json() == {"linked_record_count": 1}
    summary = tenant_api.client.get(
        f"/api/v1/prisma/reviews/{tenant_api.ids.assigned_review}/summary",
        headers=_lead_headers(tenant_api),
    ).json()
    assert summary["counts"]["records_identified_databases"] == 0
    assert summary["counts"]["records_identified_other_sources"] == 1
    assert "SEARCH_EXECUTION_NOT_RECORDED" not in {
        item["code"] for item in summary["readiness"]["blockers"]
    }
    assert partial["id"] in summary["source_references"]["search_execution_ids"]
    assert failed["id"] in summary["source_references"]["search_execution_ids"]


def test_search_execution_tenant_review_and_artifact_boundaries(
    tenant_api: TenantApi,
) -> None:
    source = _create_source(tenant_api, key="secure-source")
    execution = _create_execution(tenant_api, source["id"], result_count=0)
    artifact = tenant_api.client.post(
        f"/api/v1/search-executions/{execution['id']}/artifacts",
        params={"review_id": str(tenant_api.ids.assigned_review)},
        headers={
            **_lead_headers(tenant_api),
            "X-Original-Filename": "fixture-results.ris",
            "Content-Type": "application/x-research-info-systems",
        },
        content=b"TY  - JOUR\r\nER  -\r\n",
    )
    assert artifact.status_code == 201, artifact.text
    artifact_id = artifact.json()["id"]

    foreign_headers = tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b)
    foreign_execution = tenant_api.client.get(
        f"/api/v1/search-executions/{execution['id']}",
        params={"review_id": str(tenant_api.ids.organization_b_review)},
        headers=foreign_headers,
    )
    assert foreign_execution.status_code == 404
    foreign_artifact = tenant_api.client.get(
        f"/api/v1/search-executions/artifacts/{artifact_id}/content",
        params={"review_id": str(tenant_api.ids.organization_b_review)},
        headers=foreign_headers,
    )
    assert foreign_artifact.status_code == 404
    content = tenant_api.client.get(
        f"/api/v1/search-executions/artifacts/{artifact_id}/content",
        params={"review_id": str(tenant_api.ids.assigned_review)},
        headers=_lead_headers(tenant_api),
    )
    assert content.status_code == 200
    assert content.content == b"TY  - JOUR\r\nER  -\r\n"
    assert content.headers["x-content-sha256"] == artifact.json()["sha256"]

    reviewer_create = tenant_api.client.post(
        "/api/v1/search-executions/sources",
        headers=tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "source_key": "forbidden",
            "display_name": "Forbidden",
            "classification": "OTHER_SOURCE",
            "provider_name": "Manual",
        },
    )
    assert reviewer_create.status_code == 403

    wrong_review = tenant_api.client.get(
        f"/api/v1/search-executions/{execution['id']}",
        params={"review_id": str(tenant_api.ids.private_review)},
        headers=tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a),
    )
    assert wrong_review.status_code == 404
    cross_review_link = tenant_api.client.post(
        f"/api/v1/search-executions/{execution['id']}/imports",
        headers=tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a),
        json={
            "review_id": str(tenant_api.ids.private_review),
            "import_batch_id": "00000000-0000-0000-0000-000000000001",
        },
    )
    assert cross_review_link.status_code == 404


def test_provider_execution_is_explicitly_opt_in_and_persists_attempt_provenance(
    tenant_api: TenantApi,
) -> None:
    source = _create_source(tenant_api, key="fixture-provider")
    execution = _create_execution(
        tenant_api,
        source["id"],
        result_count=0,
        status="PLANNED",
        method="API",
        exact_query="fixture query",
    )
    payload = {
        "review_id": str(tenant_api.ids.assigned_review),
        "provider_key": "fixture",
        "max_pages": 1,
        "page_size": 1,
    }
    disabled = tenant_api.client.post(
        f"/api/v1/search-executions/{execution['id']}/provider-runs",
        headers=_lead_headers(tenant_api),
        json=payload,
    )
    assert disabled.status_code == 409

    tenant_api.settings.search_provider_execution_enabled = True
    executed = tenant_api.client.post(
        f"/api/v1/search-executions/{execution['id']}/provider-runs",
        headers=_lead_headers(tenant_api),
        json=payload,
    )
    assert executed.status_code == 200, executed.text
    body = executed.json()
    assert body["execution"]["status"] == "COMPLETED"
    assert body["provider_key"] == "fixture"
    assert body["normalized_record_count"] == 0
    assert body["attempt_count"] == 1
    assert body["artifact_id"] is not None

    attempts = tenant_api.client.get(
        f"/api/v1/search-executions/{execution['id']}/provider-attempts",
        params={"review_id": str(tenant_api.ids.assigned_review)},
        headers=_lead_headers(tenant_api),
    )
    assert attempts.status_code == 200
    assert attempts.json()[0]["provider_key"] == "fixture"
