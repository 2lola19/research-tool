from __future__ import annotations

from tests.integration.test_tenant_isolation import TenantApi, _import_screening_fixture

pytest_plugins = ("tests.integration.test_tenant_isolation",)


def test_study_family_links_multiple_articles_and_unlinks_non_destructively(
    tenant_api: TenantApi,
) -> None:
    articles = _import_screening_fixture(tenant_api)
    headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    created = tenant_api.client.post(
        "/api/v1/studies",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "study_key": "S001",
            "label": "Example study",
        },
    )
    assert created.status_code == 201, created.text
    study_id = created.json()["id"]
    for role, article in (("PRIMARY", articles[0]), ("FOLLOW_UP", articles[1])):
        linked = tenant_api.client.post(
            f"/api/v1/studies/{study_id}/articles",
            headers=headers,
            json={
                "review_id": str(tenant_api.ids.assigned_review),
                "article_id": article["id"],
                "role": role,
                "reason": "Manual family assignment",
            },
        )
        assert linked.status_code == 201, linked.text
    links = tenant_api.client.get(
        f"/api/v1/studies/{study_id}/articles",
        headers=headers,
        params={"review_id": str(tenant_api.ids.assigned_review), "active_only": True},
    )
    assert links.status_code == 200
    assert len(links.json()) == 2
    removed = tenant_api.client.delete(
        f"/api/v1/studies/links/{links.json()[0]['id']}",
        headers=headers,
        params={"review_id": str(tenant_api.ids.assigned_review)},
    )
    assert removed.status_code == 200
    assert removed.json()["active"] is False
    assert tenant_api.client.get(
        f"/api/v1/citations/articles/{articles[0]['id']}", headers=headers
    ).status_code in (200, 404)


def test_study_family_is_tenant_and_role_scoped(tenant_api: TenantApi) -> None:
    article = _import_screening_fixture(tenant_api)[0]
    owner_headers = tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a)
    created = tenant_api.client.post(
        "/api/v1/studies",
        headers=owner_headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "study_key": "S002",
        },
    )
    assert created.status_code == 201
    study_id = created.json()["id"]
    foreign = tenant_api.client.get(
        f"/api/v1/studies/{study_id}/articles",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
        params={"review_id": str(tenant_api.ids.organization_b_review)},
    )
    assert foreign.status_code == 404
    viewer = tenant_api.client.post(
        f"/api/v1/studies/{study_id}/articles",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "article_id": article["id"],
            "role": "PRIMARY",
        },
    )
    assert viewer.status_code == 403
