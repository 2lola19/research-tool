from __future__ import annotations

from tests.integration.test_documents import _upload_document
from tests.integration.test_tenant_isolation import (
    TenantApi,
    _approved_protocol,
    _assign_screening_article,
    _create_screening_round,
    _import_dedup_fixture,
    _import_screening_fixture,
)

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def _complete_title_round(
    tenant_api: TenantApi,
    articles: list[dict[str, object]],
    *,
    included_indexes: frozenset[int] = frozenset({0}),
) -> dict[str, object]:
    title_round = _create_screening_round(
        tenant_api, name="PRISMA title abstract", stage="TITLE_ABSTRACT"
    )
    for index, article in enumerate(articles):
        for reviewer_id in (tenant_api.ids.lead_a, tenant_api.ids.reviewer_a):
            assignment = _assign_screening_article(
                tenant_api,
                round_id=title_round["id"],
                article_id=article["id"],
                reviewer_id=reviewer_id,
            )
            decision = "INCLUDE" if index in included_indexes else "EXCLUDE"
            response = tenant_api.client.post(
                f"/api/v1/screening/assignments/{assignment['id']}/decision",
                headers=tenant_api.headers(
                    reviewer_id,
                    tenant_api.ids.organization_a,
                ),
                json={
                    "decision": decision,
                    **({"exclusion_reason": "Not eligible"} if decision == "EXCLUDE" else {}),
                },
            )
            assert response.status_code == 200, response.text
    close = tenant_api.client.post(
        f"/api/v1/screening/rounds/{title_round['id']}/close",
        headers=tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
    )
    assert close.status_code == 200, close.text
    return title_round


def test_prisma_summary_distinguishes_records_reports_and_studies(
    tenant_api: TenantApi,
) -> None:
    articles = _import_screening_fixture(tenant_api)
    title_round = _complete_title_round(tenant_api, articles)
    full_round = _create_screening_round(tenant_api, name="PRISMA full text", stage="FULL_TEXT")
    progression = tenant_api.client.post(
        f"/api/v1/screening/rounds/{title_round['id']}/progressions",
        headers=tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
        json={"target_round_id": full_round["id"]},
    )
    assert progression.status_code == 201, progression.text
    unavailable = tenant_api.client.post(
        f"/api/v1/documents/reviews/{tenant_api.ids.assigned_review}/articles/{articles[0]['id']}/retrieval-record",
        headers=tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
        json={
            "status": "NOT_FOUND",
            "retrieval_method": "MANUAL",
            "source_name": "Fixture retrieval",
        },
    )
    assert unavailable.status_code == 201, unavailable.text

    headers = tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a)
    response = tenant_api.client.get(
        f"/api/v1/prisma/reviews/{tenant_api.ids.assigned_review}/summary",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    counts = response.json()["counts"]
    assert counts["records_identified_databases"] == 2
    assert counts["records_screened"] == 2
    assert counts["records_excluded_title_abstract"] == 1
    assert counts["reports_sought_for_retrieval"] == 1
    assert counts["reports_not_retrieved"] == 1
    assert counts["reports_assessed_for_eligibility"] == 0
    readiness = response.json()["readiness"]
    assert readiness["ready_for_final"] is False
    assert any(item["code"] == "SEARCH_EXECUTION_NOT_RECORDED" for item in readiness["blockers"])


def test_prisma_counts_reports_studies_and_structured_exclusion_reasons(
    tenant_api: TenantApi,
) -> None:
    articles = _import_screening_fixture(tenant_api)
    title_round = _complete_title_round(tenant_api, articles, included_indexes=frozenset({0, 1}))
    full_round = _create_screening_round(
        tenant_api, name="PRISMA complete full text", stage="FULL_TEXT"
    )
    lead_headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    progression = tenant_api.client.post(
        f"/api/v1/screening/rounds/{title_round['id']}/progressions",
        headers=lead_headers,
        json={"target_round_id": full_round["id"]},
    )
    assert progression.status_code == 201, progression.text
    protocol_id = _approved_protocol(
        tenant_api,
        user_id=tenant_api.ids.lead_a,
        review_id=tenant_api.ids.assigned_review,
        suffix="prisma-complete",
    )
    documents = [_upload_document(tenant_api, article["id"]) for article in articles]
    for index, document in enumerate(documents):
        processed = tenant_api.client.post(
            f"/api/v1/documents/{document['id']}/process", headers=lead_headers
        )
        assert processed.status_code == 200, processed.text
        judgments = [
            {
                "criterion_key": "population",
                "decision": "PASS" if index == 0 else "FAIL",
                **({"reason": "Ineligible population"} if index == 1 else {}),
            },
            {"criterion_key": "outcome", "decision": "PASS"},
        ]
        screened = tenant_api.client.post(
            f"/api/v1/documents/{document['id']}/full-text-screening",
            headers=tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a),
            json={"protocol_version_id": protocol_id, "judgments": judgments},
        )
        assert screened.status_code == 200, screened.text
    study = tenant_api.client.post(
        "/api/v1/studies",
        headers=lead_headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "study_key": "PRISMA-S001",
            "label": "Included investigation",
        },
    )
    assert study.status_code == 201, study.text
    linked = tenant_api.client.post(
        f"/api/v1/studies/{study.json()['id']}/articles",
        headers=lead_headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "article_id": articles[0]["id"],
            "role": "PRIMARY",
            "reason": "Manual PRISMA fixture assignment",
        },
    )
    assert linked.status_code == 201, linked.text
    response = tenant_api.client.get(
        f"/api/v1/prisma/reviews/{tenant_api.ids.assigned_review}/summary",
        headers=lead_headers,
    )
    assert response.status_code == 200, response.text
    counts = response.json()["counts"]
    assert counts["records_identified_databases"] == 2
    assert counts["reports_sought_for_retrieval"] == 2
    assert counts["reports_assessed_for_eligibility"] == 2
    assert counts["reports_excluded_full_text"] == 1
    assert counts["studies_included_review"] == 1
    assert counts["reports_of_included_studies"] == 1
    assert counts["full_text_exclusion_reasons"] == {"population": 1}


def test_prisma_snapshots_are_reproducible_and_tenant_scoped(tenant_api: TenantApi) -> None:
    _import_screening_fixture(tenant_api)
    lead_headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    created = tenant_api.client.post(
        f"/api/v1/prisma/reviews/{tenant_api.ids.assigned_review}/snapshots",
        headers=lead_headers,
    )
    assert created.status_code == 201, created.text
    snapshot = created.json()
    listed = tenant_api.client.get(
        f"/api/v1/prisma/reviews/{tenant_api.ids.assigned_review}/snapshots",
        headers=lead_headers,
    )
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == snapshot["id"]
    foreign = tenant_api.client.get(
        f"/api/v1/prisma/snapshots/{snapshot['id']}",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
        params={"review_id": str(tenant_api.ids.organization_b_review)},
    )
    assert foreign.status_code == 404
    viewer = tenant_api.client.post(
        f"/api/v1/prisma/reviews/{tenant_api.ids.assigned_review}/snapshots",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
    )
    assert viewer.status_code == 403


def test_prisma_duplicate_removal_counts_suppressed_source_records_once(
    tenant_api: TenantApi,
) -> None:
    _import_dedup_fixture(tenant_api)
    headers = tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a)
    run = tenant_api.client.post(
        f"/api/v1/deduplication/reviews/{tenant_api.ids.assigned_review}/runs",
        headers=headers,
    )
    assert run.status_code == 201, run.text
    candidates = tenant_api.client.get(
        f"/api/v1/deduplication/reviews/{tenant_api.ids.assigned_review}/candidates",
        headers=headers,
    )
    candidate = candidates.json()[0]
    decision = tenant_api.client.post(
        f"/api/v1/deduplication/candidates/{candidate['id']}/decision",
        headers=headers,
        json={
            "decision": "CONFIRMED_DUPLICATE",
            "retained_article_id": candidate["left_article_id"],
            "reason": "Exact DOI fixture",
        },
    )
    assert decision.status_code == 200, decision.text
    summary = tenant_api.client.get(
        f"/api/v1/prisma/reviews/{tenant_api.ids.assigned_review}/summary",
        headers=headers,
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["counts"]["records_identified_databases"] == 3
    assert summary.json()["counts"]["records_removed_duplicates"] == 1
    references = summary.json()["source_references"]
    assert references["deduplication_candidate_ids"] == [candidate["id"]]
    assert references["deduplication_decision_ids"] == [decision.json()["id"]]
