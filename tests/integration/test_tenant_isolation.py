from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.api.dependencies import build_authentication_provider
from backend.app.citations.persistence import CitationImportBatchRecord
from backend.app.core.config import Settings
from backend.app.db import models as database_models
from backend.app.db.base import Base
from backend.app.db.session import get_db_session
from backend.app.identity.domain import ActorContext, OrganizationRole
from backend.app.identity.persistence import (
    LocalCredentialRecord,
    MembershipRecord,
    OrganizationRecord,
    SqlAlchemyIdentityRepository,
    UserRecord,
)
from backend.app.identity.security import ScryptPasswordHasher
from backend.app.main import create_app
from backend.app.protocols.persistence import ProtocolVersionRecord
from backend.app.provenance.persistence import (
    AuditEventRecord,
    SqlAlchemyProvenanceRepository,
)
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.persistence import (
    ReviewMembershipRecord,
    ReviewRecord,
    SqlAlchemyReviewRepository,
)

PASSWORD = "correct horse battery staple"


@dataclass(frozen=True)
class TenantIds:
    organization_a: UUID
    organization_b: UUID
    owner_a: UUID
    owner_b: UUID
    administrator_a: UUID
    lead_a: UUID
    reviewer_a: UUID
    statistician_a: UUID
    viewer_a: UUID
    removed_a: UUID
    outsider_b: UUID
    assigned_review: UUID
    private_review: UUID
    delegated_review: UUID
    organization_b_review: UUID


@dataclass
class TenantApi:
    client: TestClient
    settings: Settings
    ids: TenantIds

    def token(self, user_id: UUID) -> str:
        return build_authentication_provider(self.settings).issue_token(user_id)

    def headers(self, user_id: UUID, organization_id: UUID) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token(user_id)}",
            "X-Organization-ID": str(organization_id),
        }


async def _seed(session_factory: async_sessionmaker[AsyncSession]) -> TenantIds:
    organization_a = OrganizationRecord(name="Alpha Research", slug="alpha-research")
    organization_b = OrganizationRecord(name="Beta Research", slug="beta-research")
    users = {
        "owner_a": UserRecord(email="owner-a@example.test", display_name="Owner A"),
        "owner_b": UserRecord(email="owner-b@example.test", display_name="Owner B"),
        "administrator_a": UserRecord(
            email="administrator-a@example.test",
            display_name="Administrator A",
        ),
        "lead_a": UserRecord(email="lead-a@example.test", display_name="Lead A"),
        "reviewer_a": UserRecord(email="reviewer-a@example.test", display_name="Reviewer A"),
        "statistician_a": UserRecord(
            email="statistician-a@example.test",
            display_name="Statistician A",
        ),
        "viewer_a": UserRecord(email="viewer-a@example.test", display_name="Viewer A"),
        "removed_a": UserRecord(email="removed-a@example.test", display_name="Removed A"),
        "outsider_b": UserRecord(email="outsider-b@example.test", display_name="Outsider B"),
    }
    async with session_factory() as session:
        session.add_all([organization_a, organization_b, *users.values()])
        await session.flush()
        memberships = {
            "owner_a": MembershipRecord(
                organization_id=organization_a.id,
                user_id=users["owner_a"].id,
                role=OrganizationRole.OWNER,
            ),
            "owner_b": MembershipRecord(
                organization_id=organization_b.id,
                user_id=users["owner_b"].id,
                role=OrganizationRole.OWNER,
            ),
            "administrator_a": MembershipRecord(
                organization_id=organization_a.id,
                user_id=users["administrator_a"].id,
                role=OrganizationRole.ADMINISTRATOR,
            ),
            "lead_a": MembershipRecord(
                organization_id=organization_a.id,
                user_id=users["lead_a"].id,
                role=OrganizationRole.LEAD_REVIEWER,
            ),
            "reviewer_a": MembershipRecord(
                organization_id=organization_a.id,
                user_id=users["reviewer_a"].id,
                role=OrganizationRole.REVIEWER,
            ),
            "statistician_a": MembershipRecord(
                organization_id=organization_a.id,
                user_id=users["statistician_a"].id,
                role=OrganizationRole.STATISTICIAN,
            ),
            "viewer_a": MembershipRecord(
                organization_id=organization_a.id,
                user_id=users["viewer_a"].id,
                role=OrganizationRole.VIEWER,
            ),
            "removed_a": MembershipRecord(
                organization_id=organization_a.id,
                user_id=users["removed_a"].id,
                role=OrganizationRole.REVIEWER,
                removed_at=datetime.now(UTC),
                removed_by_user_id=users["owner_a"].id,
            ),
            "outsider_b": MembershipRecord(
                organization_id=organization_b.id,
                user_id=users["outsider_b"].id,
                role=OrganizationRole.REVIEWER,
            ),
        }
        session.add_all(memberships.values())
        password_hash = ScryptPasswordHasher().hash_password(PASSWORD)
        session.add_all(
            LocalCredentialRecord(user_id=user.id, password_hash=password_hash)
            for user in users.values()
        )
        await session.flush()

        assigned_review = ReviewRecord(
            organization_id=organization_a.id,
            title="Assigned review",
            project_slug="assigned-review",
            owner_user_id=users["lead_a"].id,
            created_by_user_id=users["lead_a"].id,
        )
        private_review = ReviewRecord(
            organization_id=organization_a.id,
            title="Private review",
            project_slug="private-review",
            owner_user_id=users["owner_a"].id,
            created_by_user_id=users["owner_a"].id,
        )
        delegated_review = ReviewRecord(
            organization_id=organization_a.id,
            title="Delegated review",
            project_slug="delegated-review",
            owner_user_id=users["owner_a"].id,
            created_by_user_id=users["owner_a"].id,
        )
        organization_b_review = ReviewRecord(
            organization_id=organization_b.id,
            title="Organization B review",
            project_slug="organization-b-review",
            owner_user_id=users["owner_b"].id,
            created_by_user_id=users["owner_b"].id,
        )
        session.add_all([assigned_review, private_review, delegated_review, organization_b_review])
        await session.flush()
        session.add_all(
            [
                ReviewMembershipRecord(
                    review_id=assigned_review.id,
                    organization_id=organization_a.id,
                    user_id=users["reviewer_a"].id,
                    assigned_by_user_id=users["lead_a"].id,
                ),
                ReviewMembershipRecord(
                    review_id=assigned_review.id,
                    organization_id=organization_a.id,
                    user_id=users["statistician_a"].id,
                    assigned_by_user_id=users["lead_a"].id,
                ),
                ReviewMembershipRecord(
                    review_id=assigned_review.id,
                    organization_id=organization_a.id,
                    user_id=users["viewer_a"].id,
                    assigned_by_user_id=users["lead_a"].id,
                ),
                ReviewMembershipRecord(
                    review_id=delegated_review.id,
                    organization_id=organization_a.id,
                    user_id=users["lead_a"].id,
                    assigned_by_user_id=users["owner_a"].id,
                ),
            ]
        )
        await session.commit()

    return TenantIds(
        organization_a=organization_a.id,
        organization_b=organization_b.id,
        owner_a=users["owner_a"].id,
        owner_b=users["owner_b"].id,
        administrator_a=users["administrator_a"].id,
        lead_a=users["lead_a"].id,
        reviewer_a=users["reviewer_a"].id,
        statistician_a=users["statistician_a"].id,
        viewer_a=users["viewer_a"].id,
        removed_a=users["removed_a"].id,
        outsider_b=users["outsider_b"].id,
        assigned_review=assigned_review.id,
        private_review=private_review.id,
        delegated_review=delegated_review.id,
        organization_b_review=organization_b_review.id,
    )


@pytest.fixture
def tenant_api(tmp_path: Path) -> TenantApi:
    _ = database_models
    postgresql_url = os.environ.get("POSTGRES_TEST_DATABASE_URL")
    database_url = postgresql_url or f"sqlite+aiosqlite:///{(tmp_path / 'tenant.db').as_posix()}"
    previous_event_loop_policy = asyncio.get_event_loop_policy()
    if postgresql_url and sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    engine = create_async_engine(database_url, poolclass=NullPool)

    if postgresql_url is None:

        @event.listens_for(engine.sync_engine, "connect")
        def enable_foreign_keys(dbapi_connection: object, _: object) -> None:
            dbapi_connection.execute("PRAGMA foreign_keys=ON")  # type: ignore[attr-defined]

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare() -> TenantIds:
        if postgresql_url is None:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        else:
            table_names = ", ".join(f'"{name}"' for name in Base.metadata.tables)
            async with engine.begin() as connection:
                await connection.execute(
                    text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE")
                )
        return await _seed(session_factory)

    try:
        ids = asyncio.run(prepare())
        settings = Settings(
            app_env="test",
            database_url=database_url,
            local_auth_secret="test-local-authentication-secret",
        )
        app = create_app(settings)

        async def override_session() -> object:
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db_session] = override_session
        with TestClient(app, raise_server_exceptions=False) as client:
            yield TenantApi(client=client, settings=settings, ids=ids)
    finally:
        asyncio.run(engine.dispose())
        if postgresql_url and sys.platform == "win32":
            asyncio.set_event_loop_policy(previous_event_loop_policy)


def test_local_login_and_authenticated_actor_context(tenant_api: TenantApi) -> None:
    login = tenant_api.client.post(
        "/api/v1/auth/token",
        json={"email": "OWNER-A@EXAMPLE.TEST", "password": PASSWORD},
    )
    assert login.status_code == 200

    response = tenant_api.client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {login.json()['access_token']}",
            "X-Organization-ID": str(tenant_api.ids.organization_a),
        },
    )
    assert response.status_code == 200
    assert response.json()["role"] == "owner"


def test_same_organization_read_access(tenant_api: TenantApi) -> None:
    response = tenant_api.client.get(
        f"/api/v1/reviews/{tenant_api.ids.assigned_review}",
        headers=tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a),
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Assigned review"


def test_same_organization_write_access(tenant_api: TenantApi) -> None:
    response = tenant_api.client.patch(
        f"/api/v1/reviews/{tenant_api.ids.assigned_review}",
        headers=tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a),
        json={"title": "Reviewer update", "project_slug": "assigned-review"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Reviewer update"


def test_cross_organization_read_is_indistinguishable_from_missing(
    tenant_api: TenantApi,
) -> None:
    response = tenant_api.client.get(
        f"/api/v1/reviews/{tenant_api.ids.organization_b_review}",
        headers=tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_cross_organization_write_is_rejected(tenant_api: TenantApi) -> None:
    response = tenant_api.client.patch(
        f"/api/v1/reviews/{tenant_api.ids.organization_b_review}",
        headers=tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a),
        json={"title": "Cross-tenant update", "project_slug": "cross-tenant-update"},
    )
    assert response.status_code == 404


def test_review_enumeration_is_tenant_and_assignment_scoped(tenant_api: TenantApi) -> None:
    owner_response = tenant_api.client.get(
        "/api/v1/reviews",
        headers=tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a),
    )
    owner_ids = {item["id"] for item in owner_response.json()}
    assert str(tenant_api.ids.organization_b_review) not in owner_ids
    assert owner_ids == {
        str(tenant_api.ids.assigned_review),
        str(tenant_api.ids.private_review),
        str(tenant_api.ids.delegated_review),
    }

    reviewer_response = tenant_api.client.get(
        "/api/v1/reviews",
        headers=tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a),
    )
    assert [item["id"] for item in reviewer_response.json()] == [
        str(tenant_api.ids.assigned_review)
    ]


@pytest.mark.parametrize("organization_header", [None, "not-a-uuid"])
def test_invalid_organization_context_is_rejected(
    tenant_api: TenantApi,
    organization_header: str | None,
) -> None:
    headers = {"Authorization": f"Bearer {tenant_api.token(tenant_api.ids.owner_a)}"}
    if organization_header is not None:
        headers["X-Organization-ID"] = organization_header
    response = tenant_api.client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_organization_context"


def test_missing_membership_is_rejected(tenant_api: TenantApi) -> None:
    response = tenant_api.client.get(
        "/api/v1/auth/me",
        headers=tenant_api.headers(tenant_api.ids.outsider_b, tenant_api.ids.organization_a),
    )
    assert response.status_code == 403


def test_removed_membership_is_rejected(tenant_api: TenantApi) -> None:
    response = tenant_api.client.get(
        "/api/v1/reviews",
        headers=tenant_api.headers(tenant_api.ids.removed_a, tenant_api.ids.organization_a),
    )
    assert response.status_code == 403


def test_membership_removal_revokes_existing_token(tenant_api: TenantApi) -> None:
    token = tenant_api.token(tenant_api.ids.reviewer_a)
    removal = tenant_api.client.delete(
        f"/api/v1/organizations/current/memberships/{tenant_api.ids.reviewer_a}",
        headers=tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a),
    )
    assert removal.status_code == 204

    response = tenant_api.client.get(
        "/api/v1/reviews",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": str(tenant_api.ids.organization_a),
        },
    )
    assert response.status_code == 403


def test_role_restrictions_block_viewer_updates_and_reviewer_creation(
    tenant_api: TenantApi,
) -> None:
    viewer_update = tenant_api.client.patch(
        f"/api/v1/reviews/{tenant_api.ids.assigned_review}",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
        json={"title": "Viewer update", "project_slug": "assigned-review"},
    )
    assert viewer_update.status_code == 403

    reviewer_create = tenant_api.client.post(
        "/api/v1/reviews",
        headers=tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a),
        json={"title": "Unauthorized project", "project_slug": "unauthorized-project"},
    )
    assert reviewer_create.status_code == 403

    statistician_update = tenant_api.client.patch(
        f"/api/v1/reviews/{tenant_api.ids.assigned_review}",
        headers=tenant_api.headers(
            tenant_api.ids.statistician_a,
            tenant_api.ids.organization_a,
        ),
        json={"title": "Statistician update", "project_slug": "assigned-review"},
    )
    assert statistician_update.status_code == 403


def test_administrator_can_manage_all_organization_reviews(tenant_api: TenantApi) -> None:
    response = tenant_api.client.post(
        f"/api/v1/reviews/{tenant_api.ids.private_review}/memberships",
        headers=tenant_api.headers(
            tenant_api.ids.administrator_a,
            tenant_api.ids.organization_a,
        ),
        json={"user_id": str(tenant_api.ids.viewer_a)},
    )
    assert response.status_code == 204


def test_review_ownership_boundary_blocks_non_owner_lead_access_management(
    tenant_api: TenantApi,
) -> None:
    response = tenant_api.client.post(
        f"/api/v1/reviews/{tenant_api.ids.delegated_review}/memberships",
        headers=tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
        json={"user_id": str(tenant_api.ids.viewer_a)},
    )
    assert response.status_code == 403


def test_unauthorized_same_tenant_review_access_returns_not_found(tenant_api: TenantApi) -> None:
    response = tenant_api.client.get(
        f"/api/v1/reviews/{tenant_api.ids.private_review}",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
    )
    assert response.status_code == 404


def test_cross_organization_review_assignment_is_rejected(tenant_api: TenantApi) -> None:
    response = tenant_api.client.post(
        f"/api/v1/reviews/{tenant_api.ids.private_review}/memberships",
        headers=tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a),
        json={"user_id": str(tenant_api.ids.outsider_b)},
    )
    assert response.status_code == 403


def test_final_owner_cannot_be_removed(tenant_api: TenantApi) -> None:
    response = tenant_api.client.delete(
        f"/api/v1/organizations/current/memberships/{tenant_api.ids.owner_a}",
        headers=tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a),
    )
    assert response.status_code == 409


def test_review_owner_membership_cannot_be_removed_without_reassignment(
    tenant_api: TenantApi,
) -> None:
    response = tenant_api.client.delete(
        f"/api/v1/organizations/current/memberships/{tenant_api.ids.lead_a}",
        headers=tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a),
    )
    assert response.status_code == 409


def test_invalid_password_does_not_reveal_account_state(tenant_api: TenantApi) -> None:
    response = tenant_api.client.post(
        "/api/v1/auth/token",
        json={"email": "owner-a@example.test", "password": "wrong password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "email or password is invalid"


def test_review_project_metadata_creation_and_uniqueness(tenant_api: TenantApi) -> None:
    headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    created = tenant_api.client.post(
        "/api/v1/reviews",
        headers=headers,
        json={
            "title": "Living evidence review",
            "project_slug": "Living-Evidence",
            "description": "  An updateable evidence synthesis.  ",
        },
    )
    assert created.status_code == 201
    assert created.json()["project_slug"] == "living-evidence"
    assert created.json()["description"] == "An updateable evidence synthesis."
    assert created.json()["archived"] is False

    duplicate = tenant_api.client.post(
        "/api/v1/reviews",
        headers=headers,
        json={"title": "Duplicate", "project_slug": "living-evidence"},
    )
    assert duplicate.status_code == 409


def test_review_project_archive_and_restore(tenant_api: TenantApi) -> None:
    headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    archived = tenant_api.client.post(
        f"/api/v1/reviews/{tenant_api.ids.assigned_review}/archive",
        headers=headers,
    )
    assert archived.status_code == 200
    assert archived.json()["archived"] is True
    assert archived.json()["archived_by_user_id"] == str(tenant_api.ids.lead_a)

    restored = tenant_api.client.delete(
        f"/api/v1/reviews/{tenant_api.ids.assigned_review}/archive",
        headers=headers,
    )
    assert restored.status_code == 200
    assert restored.json()["archived"] is False
    assert restored.json()["archived_by_user_id"] is None


def test_review_member_listing_and_removal_revokes_project_access(tenant_api: TenantApi) -> None:
    owner_headers = tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a)
    members = tenant_api.client.get(
        f"/api/v1/reviews/{tenant_api.ids.assigned_review}/memberships",
        headers=owner_headers,
    )
    assert members.status_code == 200
    assert {item["user_id"] for item in members.json()} == {
        str(tenant_api.ids.reviewer_a),
        str(tenant_api.ids.statistician_a),
        str(tenant_api.ids.viewer_a),
    }

    removed = tenant_api.client.delete(
        f"/api/v1/reviews/{tenant_api.ids.assigned_review}/memberships/{tenant_api.ids.viewer_a}",
        headers=owner_headers,
    )
    assert removed.status_code == 204
    denied = tenant_api.client.get(
        f"/api/v1/reviews/{tenant_api.ids.assigned_review}",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
    )
    assert denied.status_code == 404


def test_administrator_can_transfer_review_ownership_within_tenant(
    tenant_api: TenantApi,
) -> None:
    response = tenant_api.client.post(
        f"/api/v1/reviews/{tenant_api.ids.private_review}/ownership",
        headers=tenant_api.headers(
            tenant_api.ids.administrator_a,
            tenant_api.ids.organization_a,
        ),
        json={"user_id": str(tenant_api.ids.reviewer_a)},
    )
    assert response.status_code == 200
    assert response.json()["owner_user_id"] == str(tenant_api.ids.reviewer_a)


def test_review_ownership_transfer_cannot_cross_tenants(tenant_api: TenantApi) -> None:
    response = tenant_api.client.post(
        f"/api/v1/reviews/{tenant_api.ids.private_review}/ownership",
        headers=tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a),
        json={"user_id": str(tenant_api.ids.outsider_b)},
    )
    assert response.status_code == 403


def test_non_owner_lead_cannot_archive_delegated_review(tenant_api: TenantApi) -> None:
    response = tenant_api.client.post(
        f"/api/v1/reviews/{tenant_api.ids.delegated_review}/archive",
        headers=tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
    )
    assert response.status_code == 403


def _create_workflow_job(
    tenant_api: TenantApi,
    *,
    user_id: UUID,
    organization_id: UUID,
    review_id: UUID,
    suffix: str,
) -> tuple[str, str]:
    headers = tenant_api.headers(user_id, organization_id)
    run = tenant_api.client.post(
        "/api/v1/workflow/runs",
        headers=headers,
        json={
            "review_id": str(review_id),
            "workflow_name": "systematic-review",
            "workflow_version": "1",
            "idempotency_key": f"run-{suffix}",
        },
    )
    assert run.status_code == 201, run.text
    job = tenant_api.client.post(
        f"/api/v1/workflow/runs/{run.json()['id']}/jobs",
        headers=headers,
        json={
            "review_id": str(review_id),
            "task_name": "prepare-search",
            "task_version": "1",
            "idempotency_key": f"job-{suffix}",
            "payload": {"database": "fixture"},
        },
    )
    assert job.status_code == 201, job.text
    return run.json()["id"], job.json()["id"]


def test_workflow_submission_is_idempotent_and_input_bound(tenant_api: TenantApi) -> None:
    headers = tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a)
    payload = {
        "review_id": str(tenant_api.ids.private_review),
        "workflow_name": "systematic-review",
        "workflow_version": "1",
        "idempotency_key": "stable-run",
    }
    first = tenant_api.client.post("/api/v1/workflow/runs", headers=headers, json=payload)
    replay = tenant_api.client.post("/api/v1/workflow/runs", headers=headers, json=payload)
    assert first.status_code == replay.status_code == 201
    assert first.json()["id"] == replay.json()["id"]

    changed = tenant_api.client.post(
        "/api/v1/workflow/runs",
        headers=headers,
        json={**payload, "workflow_version": "2"},
    )
    assert changed.status_code == 409

    job_payload = {
        "review_id": str(tenant_api.ids.private_review),
        "task_name": "prepare-search",
        "task_version": "1",
        "idempotency_key": "stable-job",
        "payload": {"source": "fixture"},
    }
    first_job = tenant_api.client.post(
        f"/api/v1/workflow/runs/{first.json()['id']}/jobs",
        headers=headers,
        json=job_payload,
    )
    replay_job = tenant_api.client.post(
        f"/api/v1/workflow/runs/{first.json()['id']}/jobs",
        headers=headers,
        json=job_payload,
    )
    assert first_job.status_code == replay_job.status_code == 201
    assert first_job.json()["id"] == replay_job.json()["id"]
    changed_job = tenant_api.client.post(
        f"/api/v1/workflow/runs/{first.json()['id']}/jobs",
        headers=headers,
        json={**job_payload, "payload": {"source": "different"}},
    )
    assert changed_job.status_code == 409


def test_workflow_transitions_preserve_pause_state_and_order_events(
    tenant_api: TenantApi,
) -> None:
    _, job_id = _create_workflow_job(
        tenant_api,
        user_id=tenant_api.ids.owner_a,
        organization_id=tenant_api.ids.organization_a,
        review_id=tenant_api.ids.private_review,
        suffix="transitions",
    )
    headers = tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a)

    for target in ("RUNNING", "PAUSED"):
        response = tenant_api.client.post(
            f"/api/v1/workflow/jobs/{job_id}/transitions",
            headers=headers,
            json={"target_state": target, "reason": f"move to {target}"},
        )
        assert response.status_code == 200
    invalid_resume = tenant_api.client.post(
        f"/api/v1/workflow/jobs/{job_id}/transitions",
        headers=headers,
        json={"target_state": "QUEUED"},
    )
    assert invalid_resume.status_code == 409
    resumed = tenant_api.client.post(
        f"/api/v1/workflow/jobs/{job_id}/transitions",
        headers=headers,
        json={"target_state": "RUNNING"},
    )
    assert resumed.status_code == 200
    assert resumed.json()["paused_from_state"] is None
    assert resumed.json()["attempt"] == 2

    events = tenant_api.client.get(f"/api/v1/workflow/jobs/{job_id}/events", headers=headers)
    assert events.status_code == 200
    assert [event["sequence"] for event in events.json()] == [1, 2, 3, 4]
    assert [event["to_state"] for event in events.json()] == [
        "QUEUED",
        "RUNNING",
        "PAUSED",
        "RUNNING",
    ]


def test_workflow_resources_cannot_be_enumerated_across_tenants(
    tenant_api: TenantApi,
) -> None:
    _, job_id = _create_workflow_job(
        tenant_api,
        user_id=tenant_api.ids.owner_a,
        organization_id=tenant_api.ids.organization_a,
        review_id=tenant_api.ids.private_review,
        suffix="tenant-boundary",
    )
    foreign_headers = tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b)
    events = tenant_api.client.get(
        f"/api/v1/workflow/jobs/{job_id}/events", headers=foreign_headers
    )
    transition = tenant_api.client.post(
        f"/api/v1/workflow/jobs/{job_id}/transitions",
        headers=foreign_headers,
        json={"target_state": "RUNNING"},
    )
    assert events.status_code == transition.status_code == 404


def test_workflow_control_requires_authorized_review_controller(
    tenant_api: TenantApi,
) -> None:
    _, job_id = _create_workflow_job(
        tenant_api,
        user_id=tenant_api.ids.lead_a,
        organization_id=tenant_api.ids.organization_a,
        review_id=tenant_api.ids.assigned_review,
        suffix="roles",
    )
    reviewer_headers = tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a)
    readable = tenant_api.client.get(
        f"/api/v1/workflow/jobs/{job_id}/events", headers=reviewer_headers
    )
    denied = tenant_api.client.post(
        f"/api/v1/workflow/jobs/{job_id}/transitions",
        headers=reviewer_headers,
        json={"target_state": "RUNNING"},
    )
    assert readable.status_code == 200
    assert denied.status_code == 403


@pytest.mark.parametrize(
    ("decision", "expected_job_state"),
    [("APPROVED", "RUNNING"), ("REJECTED", "FAILED")],
)
def test_human_checkpoint_decisions_are_explicit_and_auditable(
    tenant_api: TenantApi,
    decision: str,
    expected_job_state: str,
) -> None:
    _, job_id = _create_workflow_job(
        tenant_api,
        user_id=tenant_api.ids.lead_a,
        organization_id=tenant_api.ids.organization_a,
        review_id=tenant_api.ids.assigned_review,
        suffix=f"checkpoint-{decision.casefold()}",
    )
    headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    running = tenant_api.client.post(
        f"/api/v1/workflow/jobs/{job_id}/transitions",
        headers=headers,
        json={"target_state": "RUNNING"},
    )
    assert running.status_code == 200
    requested = tenant_api.client.post(
        f"/api/v1/workflow/jobs/{job_id}/checkpoints",
        headers=headers,
        json={"request_message": "Confirm the human-reviewed decision."},
    )
    assert requested.status_code == 201
    assert requested.json()["state"] == "PENDING"
    resolved = tenant_api.client.post(
        f"/api/v1/workflow/checkpoints/{requested.json()['id']}/decision",
        headers=headers,
        json={"decision": decision, "decision_note": "Reviewed by the lead."},
    )
    assert resolved.status_code == 200
    assert resolved.json()["state"] == decision

    events = tenant_api.client.get(f"/api/v1/workflow/jobs/{job_id}/events", headers=headers)
    assert events.status_code == 200
    assert events.json()[-1]["to_state"] == expected_job_state
    assert [event["event_type"] for event in events.json()][-3:] == [
        "CHECKPOINT_REQUESTED",
        "CHECKPOINT_RESOLVED",
        "STATE_CHANGED",
    ]


def _create_prompt_version(tenant_api: TenantApi, user_id: UUID, suffix: str) -> dict[str, object]:
    response = tenant_api.client.post(
        "/api/v1/provenance/prompts",
        headers=tenant_api.headers(user_id, tenant_api.ids.organization_a),
        json={
            "prompt_key": f"screening-{suffix}",
            "template": "Return a fixture-only structured decision.",
            "output_schema": {"type": "object"},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_prompt_versions_are_immutable_numbered_records(tenant_api: TenantApi) -> None:
    headers = tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a)
    payload = {
        "prompt_key": "screening-decision",
        "template": "Fixture prompt version one.",
        "output_schema": {"type": "object"},
    }
    first = tenant_api.client.post("/api/v1/provenance/prompts", headers=headers, json=payload)
    second = tenant_api.client.post(
        "/api/v1/provenance/prompts",
        headers=headers,
        json={**payload, "template": "Fixture prompt version two."},
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["version"] == 1
    assert second.json()["version"] == 2
    assert first.json()["id"] != second.json()["id"]


def test_ai_run_and_scientific_provenance_are_captured_and_tenant_scoped(
    tenant_api: TenantApi,
) -> None:
    prompt = _create_prompt_version(tenant_api, tenant_api.ids.lead_a, "ai-capture")
    lead_headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    ai_run = tenant_api.client.post(
        "/api/v1/provenance/ai-runs",
        headers=lead_headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "prompt_version_id": prompt["id"],
            "provider": "mock",
            "model_name": "deterministic-fixture",
            "model_version": "1",
            "parameters": {"temperature": 0},
            "input_snapshot": {"citation_id": "fixture-1"},
            "output_snapshot": {"decision": "NEEDS_REVIEW"},
            "status": "SUCCEEDED",
            "usage": {"input_units": 1, "output_units": 1},
        },
    )
    assert ai_run.status_code == 201, ai_run.text
    subject_id = uuid4()
    source_id = uuid4()
    recorded = tenant_api.client.post(
        f"/api/v1/provenance/reviews/{tenant_api.ids.assigned_review}/records",
        headers=lead_headers,
        json={
            "subject_type": "screening_suggestion",
            "subject_id": str(subject_id),
            "source_type": "article",
            "source_id": str(source_id),
            "source_locator": {"field": "abstract"},
            "method_name": "fixture-screening",
            "method_version": "1",
            "actor_kind": "AI",
            "ai_run_id": ai_run.json()["id"],
            "confidence": 0.5,
        },
    )
    assert recorded.status_code == 201, recorded.text
    assert recorded.json()["actor_user_id"] is None

    reviewer_list = tenant_api.client.get(
        f"/api/v1/provenance/reviews/{tenant_api.ids.assigned_review}/records",
        headers=tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a),
    )
    foreign_list = tenant_api.client.get(
        f"/api/v1/provenance/reviews/{tenant_api.ids.assigned_review}/records",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    assert reviewer_list.status_code == 200
    assert [item["subject_id"] for item in reviewer_list.json()] == [str(subject_id)]
    assert foreign_list.status_code == 404
    audit = tenant_api.client.get(
        f"/api/v1/provenance/reviews/{tenant_api.ids.assigned_review}/audit",
        headers=lead_headers,
    )
    assert audit.status_code == 200
    assert {event["entity_type"] for event in audit.json()} == {
        "ai_run",
        "scientific_provenance",
    }


def test_human_provenance_records_current_actor_and_role_rules(
    tenant_api: TenantApi,
) -> None:
    statistician_headers = tenant_api.headers(
        tenant_api.ids.statistician_a, tenant_api.ids.organization_a
    )
    recorded = tenant_api.client.post(
        f"/api/v1/provenance/reviews/{tenant_api.ids.assigned_review}/records",
        headers=statistician_headers,
        json={
            "subject_type": "analysis_note",
            "subject_id": str(uuid4()),
            "source_locator": {},
            "method_name": "manual-verification",
            "method_version": "1",
            "actor_kind": "HUMAN",
            "verification_state": "HUMAN_VERIFIED",
        },
    )
    assert recorded.status_code == 201
    assert recorded.json()["actor_user_id"] == str(tenant_api.ids.statistician_a)

    viewer_attempt = tenant_api.client.post(
        f"/api/v1/provenance/reviews/{tenant_api.ids.assigned_review}/records",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
        json={
            "subject_type": "analysis_note",
            "subject_id": str(uuid4()),
            "source_locator": {},
            "method_name": "manual-verification",
            "method_version": "1",
            "actor_kind": "HUMAN",
        },
    )
    assert viewer_attempt.status_code == 403


def test_ai_provenance_cannot_reference_another_review_or_tenant(
    tenant_api: TenantApi,
) -> None:
    prompt = _create_prompt_version(tenant_api, tenant_api.ids.owner_a, "scope")
    headers = tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a)
    ai_run = tenant_api.client.post(
        "/api/v1/provenance/ai-runs",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.private_review),
            "prompt_version_id": prompt["id"],
            "provider": "mock",
            "model_name": "fixture",
            "model_version": "1",
            "input_snapshot": {},
            "status": "FAILED",
        },
    )
    assert ai_run.status_code == 201
    mismatch = tenant_api.client.post(
        f"/api/v1/provenance/reviews/{tenant_api.ids.assigned_review}/records",
        headers=headers,
        json={
            "subject_type": "suggestion",
            "subject_id": str(uuid4()),
            "source_locator": {},
            "method_name": "fixture",
            "method_version": "1",
            "actor_kind": "AI",
            "ai_run_id": ai_run.json()["id"],
        },
    )
    assert mismatch.status_code == 404


def test_audit_ledger_rejects_update_mutation(tenant_api: TenantApi) -> None:
    async def exercise() -> None:
        engine = create_async_engine(str(tenant_api.settings.database_url), poolclass=NullPool)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                membership = (
                    await session.scalars(
                        select(MembershipRecord).where(
                            MembershipRecord.organization_id == tenant_api.ids.organization_a,
                            MembershipRecord.user_id == tenant_api.ids.owner_a,
                        )
                    )
                ).one()
                actor = ActorContext(
                    user_id=tenant_api.ids.owner_a,
                    organization_id=tenant_api.ids.organization_a,
                    membership_id=membership.id,
                    role=OrganizationRole.OWNER,
                )
                service = ProvenanceService(
                    SqlAlchemyProvenanceRepository(session),
                    SqlAlchemyReviewRepository(session),
                    SqlAlchemyIdentityRepository(session),
                )
                event_record = await service.record_audit_event(
                    actor,
                    review_id=tenant_api.ids.private_review,
                    entity_type="review",
                    entity_id=tenant_api.ids.private_review,
                    action="created",
                    before_snapshot=None,
                    after_snapshot={"title": "Private review"},
                    reason=None,
                )
                await session.commit()
                stored = await session.get(AuditEventRecord, event_record.id)
                assert stored is not None
                stored.action = "tampered"
                with pytest.raises(TypeError, match="append-only"):
                    await session.commit()
                await session.rollback()
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def _protocol_content(title: str) -> dict[str, object]:
    return {
        "title": title,
        "objective": "Evaluate a predefined fixture intervention.",
        "research_question": {
            "population": "Adults",
            "intervention": "Fixture intervention",
            "comparator": "Usual care",
            "outcomes": ["Primary fixture outcome"],
        },
        "eligibility": {
            "inclusion": ["Randomized studies"],
            "exclusion": ["Non-human studies"],
        },
        "primary_outcomes": ["Primary fixture outcome"],
        "secondary_outcomes": [],
        "study_designs": ["Randomized controlled trial"],
        "analysis_plan": "Use a deterministic predefined synthesis plan.",
    }


def test_protocol_versions_and_approval_are_immutable_and_provenanced(
    tenant_api: TenantApi,
) -> None:
    headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    first = tenant_api.client.post(
        "/api/v1/protocols/versions",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "content": _protocol_content("Protocol one"),
        },
    )
    assert first.status_code == 201, first.text
    assert first.json()["version"] == 1
    assert len(first.json()["content_hash"]) == 64

    approval = tenant_api.client.post(
        f"/api/v1/protocols/versions/{first.json()['id']}/decision",
        headers=headers,
        json={"decision": "APPROVED", "reason": "Human review complete."},
    )
    assert approval.status_code == 200, approval.text
    duplicate = tenant_api.client.post(
        f"/api/v1/protocols/versions/{first.json()['id']}/decision",
        headers=headers,
        json={"decision": "REJECTED", "reason": "Cannot replace the decision."},
    )
    assert duplicate.status_code == 409

    second = tenant_api.client.post(
        "/api/v1/protocols/versions",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "content": _protocol_content("Protocol two"),
        },
    )
    assert second.status_code == 201
    assert second.json()["version"] == 2
    versions = tenant_api.client.get(
        f"/api/v1/protocols/reviews/{tenant_api.ids.assigned_review}/versions",
        headers=headers,
    )
    assert versions.status_code == 200
    assert [version["decision"] for version in versions.json()] == ["APPROVED", None]
    assert versions.json()[0]["content"]["title"] == "Protocol one"

    provenance = tenant_api.client.get(
        f"/api/v1/provenance/reviews/{tenant_api.ids.assigned_review}/records",
        headers=headers,
    )
    matching = [
        record for record in provenance.json() if record["subject_id"] == first.json()["id"]
    ]
    assert len(matching) == 1
    assert matching[0]["verification_state"] == "HUMAN_VERIFIED"


def test_protocol_management_enforces_review_ownership_and_roles(
    tenant_api: TenantApi,
) -> None:
    reviewer_attempt = tenant_api.client.post(
        "/api/v1/protocols/versions",
        headers=tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "content": _protocol_content("Unauthorized"),
        },
    )
    non_owner_lead = tenant_api.client.post(
        "/api/v1/protocols/versions",
        headers=tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
        json={
            "review_id": str(tenant_api.ids.delegated_review),
            "content": _protocol_content("Delegated"),
        },
    )
    assert reviewer_attempt.status_code == non_owner_lead.status_code == 403


def test_protocol_resources_are_not_enumerable_across_tenants(
    tenant_api: TenantApi,
) -> None:
    owner_headers = tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a)
    created = tenant_api.client.post(
        "/api/v1/protocols/versions",
        headers=owner_headers,
        json={
            "review_id": str(tenant_api.ids.private_review),
            "content": _protocol_content("Private protocol"),
        },
    )
    assert created.status_code == 201
    foreign_headers = tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b)
    foreign_list = tenant_api.client.get(
        f"/api/v1/protocols/reviews/{tenant_api.ids.private_review}/versions",
        headers=foreign_headers,
    )
    foreign_decision = tenant_api.client.post(
        f"/api/v1/protocols/versions/{created.json()['id']}/decision",
        headers=foreign_headers,
        json={"decision": "APPROVED"},
    )
    assert foreign_list.status_code == foreign_decision.status_code == 404


def test_protocol_rejection_requires_reason(tenant_api: TenantApi) -> None:
    headers = tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a)
    created = tenant_api.client.post(
        "/api/v1/protocols/versions",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.private_review),
            "content": _protocol_content("Rejected protocol"),
        },
    )
    rejected = tenant_api.client.post(
        f"/api/v1/protocols/versions/{created.json()['id']}/decision",
        headers=headers,
        json={"decision": "REJECTED"},
    )
    assert rejected.status_code == 409


def test_protocol_version_rows_reject_mutation(tenant_api: TenantApi) -> None:
    headers = tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a)
    created = tenant_api.client.post(
        "/api/v1/protocols/versions",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.private_review),
            "content": _protocol_content("Immutable protocol"),
        },
    )
    assert created.status_code == 201

    async def exercise() -> None:
        engine = create_async_engine(str(tenant_api.settings.database_url), poolclass=NullPool)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                stored = await session.get(ProtocolVersionRecord, UUID(created.json()["id"]))
                assert stored is not None
                stored.content_hash = "0" * 64
                with pytest.raises(TypeError, match="immutable"):
                    await session.commit()
                await session.rollback()
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def _approved_protocol(
    tenant_api: TenantApi, *, user_id: UUID, review_id: UUID, suffix: str
) -> str:
    headers = tenant_api.headers(user_id, tenant_api.ids.organization_a)
    created = tenant_api.client.post(
        "/api/v1/protocols/versions",
        headers=headers,
        json={
            "review_id": str(review_id),
            "content": _protocol_content(f"Search protocol {suffix}"),
        },
    )
    assert created.status_code == 201, created.text
    approved = tenant_api.client.post(
        f"/api/v1/protocols/versions/{created.json()['id']}/decision",
        headers=headers,
        json={"decision": "APPROVED"},
    )
    assert approved.status_code == 200, approved.text
    return created.json()["id"]


def _search_content() -> dict[str, object]:
    return {
        "name": "Fixture search",
        "concepts": [
            {
                "label": "population",
                "terms": [
                    {"text": "hypertension", "field": "mesh"},
                    {"text": "high   blood pressure", "field": "title_abstract"},
                ],
            },
            {
                "label": "intervention",
                "terms": [{"text": "exercise", "field": "all"}],
            },
        ],
    }


def test_search_strategy_requires_approved_protocol_and_translates_deterministically(
    tenant_api: TenantApi,
) -> None:
    protocol_id = _approved_protocol(
        tenant_api,
        user_id=tenant_api.ids.lead_a,
        review_id=tenant_api.ids.assigned_review,
        suffix="translation",
    )
    headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    created = tenant_api.client.post(
        "/api/v1/search-strategies/versions",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "protocol_version_id": protocol_id,
            "content": _search_content(),
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["content"]["concepts"][0]["terms"][1]["text"] == ("high blood pressure")
    translated = tenant_api.client.post(
        f"/api/v1/search-strategies/versions/{created.json()['id']}/translations",
        headers=headers,
        json={"provider": "PubMed"},
    )
    replay = tenant_api.client.post(
        f"/api/v1/search-strategies/versions/{created.json()['id']}/translations",
        headers=headers,
        json={"provider": "pubmed"},
    )
    assert translated.status_code == replay.status_code == 201
    assert translated.json()["id"] == replay.json()["id"]
    assert translated.json()["query"] == (
        '("hypertension"[MeSH Terms] OR "high blood pressure"[Title/Abstract]) '
        'AND ("exercise"[All Fields])'
    )
    audit = tenant_api.client.get(
        f"/api/v1/provenance/reviews/{tenant_api.ids.assigned_review}/audit",
        headers=headers,
    )
    assert audit.status_code == 200
    audited_entities = {event["entity_type"] for event in audit.json()}
    assert {"search_strategy_version", "search_translation"} <= audited_entities


def test_unapproved_protocol_cannot_anchor_search_strategy(tenant_api: TenantApi) -> None:
    headers = tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a)
    protocol = tenant_api.client.post(
        "/api/v1/protocols/versions",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.private_review),
            "content": _protocol_content("Pending protocol"),
        },
    )
    created = tenant_api.client.post(
        "/api/v1/search-strategies/versions",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.private_review),
            "protocol_version_id": protocol.json()["id"],
            "content": _search_content(),
        },
    )
    assert created.status_code == 409


def test_search_strategy_access_is_role_review_and_tenant_scoped(
    tenant_api: TenantApi,
) -> None:
    protocol_id = _approved_protocol(
        tenant_api,
        user_id=tenant_api.ids.lead_a,
        review_id=tenant_api.ids.assigned_review,
        suffix="scope",
    )
    reviewer_headers = tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a)
    denied = tenant_api.client.post(
        "/api/v1/search-strategies/versions",
        headers=reviewer_headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "protocol_version_id": protocol_id,
            "content": _search_content(),
        },
    )
    assert denied.status_code == 403
    lead_headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    created = tenant_api.client.post(
        "/api/v1/search-strategies/versions",
        headers=lead_headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "protocol_version_id": protocol_id,
            "content": _search_content(),
        },
    )
    assert created.status_code == 201
    readable = tenant_api.client.get(
        f"/api/v1/search-strategies/reviews/{tenant_api.ids.assigned_review}/versions",
        headers=reviewer_headers,
    )
    foreign = tenant_api.client.get(
        f"/api/v1/search-strategies/reviews/{tenant_api.ids.assigned_review}/versions",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    assert readable.status_code == 200
    assert foreign.status_code == 404


def test_unsupported_search_translator_fails_without_network_fallback(
    tenant_api: TenantApi,
) -> None:
    protocol_id = _approved_protocol(
        tenant_api,
        user_id=tenant_api.ids.owner_a,
        review_id=tenant_api.ids.private_review,
        suffix="unsupported",
    )
    headers = tenant_api.headers(tenant_api.ids.owner_a, tenant_api.ids.organization_a)
    created = tenant_api.client.post(
        "/api/v1/search-strategies/versions",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.private_review),
            "protocol_version_id": protocol_id,
            "content": _search_content(),
        },
    )
    response = tenant_api.client.post(
        f"/api/v1/search-strategies/versions/{created.json()['id']}/translations",
        headers=headers,
        json={"provider": "unknown-provider"},
    )
    assert response.status_code == 409


def test_csv_citation_import_is_lossless_idempotent_and_does_not_deduplicate(
    tenant_api: TenantApi,
) -> None:
    headers = tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a)
    content = (
        "title,abstract,year,doi,pmid,authors,journal\n"
        "First article,Abstract one,2024,https://doi.org/10.1/DUP,123,A One,Journal A\n"
        "Second article,Abstract two,2024,doi: 10.1/DUP,124,B Two,Journal B\n"
    )
    payload = {
        "review_id": str(tenant_api.ids.assigned_review),
        "source_format": "CSV",
        "source_name": "fixture.csv",
        "content": content,
    }
    first = tenant_api.client.post("/api/v1/citations/imports", headers=headers, json=payload)
    replay = tenant_api.client.post("/api/v1/citations/imports", headers=headers, json=payload)
    assert first.status_code == replay.status_code == 201
    assert first.json()["id"] == replay.json()["id"]
    assert first.json()["record_count"] == 2

    articles = tenant_api.client.get(
        f"/api/v1/citations/reviews/{tenant_api.ids.assigned_review}/articles",
        headers=headers,
    )
    assert articles.status_code == 200
    imported = [item for item in articles.json() if item["doi"] == "10.1/dup"]
    assert len(imported) == 2
    assert {item["title"] for item in imported} == {"First article", "Second article"}

    async def verify_source() -> None:
        engine = create_async_engine(str(tenant_api.settings.database_url), poolclass=NullPool)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                batch = await session.get(CitationImportBatchRecord, UUID(first.json()["id"]))
                assert batch is not None
                assert batch.source_content == content
        finally:
            await engine.dispose()

    asyncio.run(verify_source())


def test_citation_import_validates_records_and_roles(tenant_api: TenantApi) -> None:
    invalid = tenant_api.client.post(
        "/api/v1/citations/imports",
        headers=tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "source_format": "CSV",
            "source_name": "invalid.csv",
            "content": "year,doi\n2024,10.1/missing-title\n",
        },
    )
    denied = tenant_api.client.post(
        "/api/v1/citations/imports",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "source_format": "RIS",
            "source_name": "viewer.ris",
            "content": "TY  - JOUR\nTI  - Viewer record\nER  -\n",
        },
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_citation_import"
    assert denied.status_code == 403


def test_citation_articles_are_review_and_tenant_scoped(tenant_api: TenantApi) -> None:
    foreign = tenant_api.client.get(
        f"/api/v1/citations/reviews/{tenant_api.ids.assigned_review}/articles",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    unauthorized_same_tenant = tenant_api.client.get(
        f"/api/v1/citations/reviews/{tenant_api.ids.private_review}/articles",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
    )
    assert foreign.status_code == unauthorized_same_tenant.status_code == 404


def _import_dedup_fixture(tenant_api: TenantApi) -> None:
    response = tenant_api.client.post(
        "/api/v1/citations/imports",
        headers=tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "source_format": "CSV",
            "source_name": "dedup.csv",
            "content": (
                "title,year,doi,pmid\n"
                "Duplicate first,2024,10.5/shared,100\n"
                "Duplicate second,2023,10.5/shared,101\n"
                "Clearly unrelated article,2020,10.5/unique,102\n"
            ),
        },
    )
    assert response.status_code == 201, response.text


def test_deduplication_is_idempotent_reviewable_and_non_destructive(
    tenant_api: TenantApi,
) -> None:
    _import_dedup_fixture(tenant_api)
    headers = tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a)
    first = tenant_api.client.post(
        f"/api/v1/deduplication/reviews/{tenant_api.ids.assigned_review}/runs",
        headers=headers,
    )
    replay = tenant_api.client.post(
        f"/api/v1/deduplication/reviews/{tenant_api.ids.assigned_review}/runs",
        headers=headers,
    )
    assert first.status_code == replay.status_code == 201
    assert first.json()["id"] == replay.json()["id"]
    assert first.json()["article_count"] == 3
    assert first.json()["candidate_count"] == 1

    candidates = tenant_api.client.get(
        f"/api/v1/deduplication/reviews/{tenant_api.ids.assigned_review}/candidates",
        headers=headers,
    )
    assert candidates.status_code == 200
    assert candidates.json()[0]["reason"] == "DOI_EXACT"
    decided = tenant_api.client.post(
        f"/api/v1/deduplication/candidates/{candidates.json()[0]['id']}/decision",
        headers=headers,
        json={
            "decision": "CONFIRMED_DUPLICATE",
            "retained_article_id": candidates.json()[0]["left_article_id"],
            "reason": "Exact normalized DOI.",
        },
    )
    duplicate_decision = tenant_api.client.post(
        f"/api/v1/deduplication/candidates/{candidates.json()[0]['id']}/decision",
        headers=headers,
        json={"decision": "REJECTED"},
    )
    assert decided.status_code == 200
    assert duplicate_decision.status_code == 409

    articles = tenant_api.client.get(
        f"/api/v1/citations/reviews/{tenant_api.ids.assigned_review}/articles",
        headers=headers,
    )
    assert len(articles.json()) == 3
    audit = tenant_api.client.get(
        f"/api/v1/provenance/reviews/{tenant_api.ids.assigned_review}/audit",
        headers=headers,
    )
    assert audit.status_code == 200
    assert any(event["entity_type"] == "deduplication_decision" for event in audit.json())


def test_deduplication_role_and_tenant_boundaries(tenant_api: TenantApi) -> None:
    _import_dedup_fixture(tenant_api)
    reviewer_headers = tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a)
    run = tenant_api.client.post(
        f"/api/v1/deduplication/reviews/{tenant_api.ids.assigned_review}/runs",
        headers=reviewer_headers,
    )
    assert run.status_code == 201
    candidates = tenant_api.client.get(
        f"/api/v1/deduplication/reviews/{tenant_api.ids.assigned_review}/candidates",
        headers=reviewer_headers,
    ).json()
    viewer_scan = tenant_api.client.post(
        f"/api/v1/deduplication/reviews/{tenant_api.ids.assigned_review}/runs",
        headers=tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a),
    )
    foreign_list = tenant_api.client.get(
        f"/api/v1/deduplication/reviews/{tenant_api.ids.assigned_review}/candidates",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    foreign_decision = tenant_api.client.post(
        f"/api/v1/deduplication/candidates/{candidates[0]['id']}/decision",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
        json={"decision": "REJECTED"},
    )
    assert viewer_scan.status_code == 403
    assert foreign_list.status_code == foreign_decision.status_code == 404


def _import_screening_fixture(tenant_api: TenantApi) -> list[dict[str, object]]:
    headers = tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a)
    imported = tenant_api.client.post(
        "/api/v1/citations/imports",
        headers=headers,
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "source_format": "CSV",
            "source_name": "screening.csv",
            "content": (
                "title,abstract,year,doi\n"
                "Progress this article,Relevant abstract,2025,10.9/progress\n"
                "Exclude this article,Irrelevant abstract,2024,10.9/exclude\n"
            ),
        },
    )
    assert imported.status_code == 201, imported.text
    articles = tenant_api.client.get(
        f"/api/v1/citations/reviews/{tenant_api.ids.assigned_review}/articles",
        headers=headers,
    )
    assert articles.status_code == 200
    return articles.json()


def _create_screening_round(tenant_api: TenantApi, *, name: str, stage: str) -> dict[str, object]:
    response = tenant_api.client.post(
        "/api/v1/screening/rounds",
        headers=tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "name": name,
            "stage": stage,
            "required_decisions": 2,
            "blinded": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_screening_rejects_unblinded_rounds_without_a_reveal_policy(
    tenant_api: TenantApi,
) -> None:
    response = tenant_api.client.post(
        "/api/v1/screening/rounds",
        headers=tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
        json={
            "review_id": str(tenant_api.ids.assigned_review),
            "name": "Unsupported unblinded round",
            "stage": "TITLE_ABSTRACT",
            "required_decisions": 2,
            "blinded": False,
        },
    )
    assert response.status_code == 409


def _assign_screening_article(
    tenant_api: TenantApi, *, round_id: object, article_id: object, reviewer_id: UUID
) -> dict[str, object]:
    response = tenant_api.client.post(
        f"/api/v1/screening/rounds/{round_id}/assignments",
        headers=tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
        json={"article_id": article_id, "reviewer_user_id": str(reviewer_id)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_blinded_screening_consensus_adjudication_and_progression(
    tenant_api: TenantApi,
) -> None:
    articles = _import_screening_fixture(tenant_api)
    by_title = {str(article["title"]): article for article in articles}
    progressed_article = by_title["Progress this article"]
    excluded_article = by_title["Exclude this article"]
    title_round = _create_screening_round(
        tenant_api, name="Title and abstract", stage="TITLE_ABSTRACT"
    )
    full_text_round = _create_screening_round(tenant_api, name="Full text", stage="FULL_TEXT")

    listed_rounds = tenant_api.client.get(
        f"/api/v1/screening/reviews/{tenant_api.ids.assigned_review}/rounds",
        headers=tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a),
    )
    assert listed_rounds.status_code == 200, listed_rounds.text
    assert [item["id"] for item in listed_rounds.json()] == [
        title_round["id"],
        full_text_round["id"],
    ]
    foreign_rounds = tenant_api.client.get(
        f"/api/v1/screening/reviews/{tenant_api.ids.assigned_review}/rounds",
        headers=tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b),
    )
    assert foreign_rounds.status_code == 404

    assignments: dict[tuple[str, UUID], dict[str, object]] = {}
    for article in (progressed_article, excluded_article):
        for reviewer_id in (tenant_api.ids.lead_a, tenant_api.ids.reviewer_a):
            assignment = _assign_screening_article(
                tenant_api,
                round_id=title_round["id"],
                article_id=article["id"],
                reviewer_id=reviewer_id,
            )
            assignments[(str(article["id"]), reviewer_id)] = assignment

    lead_headers = tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a)
    reviewer_headers = tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a)
    lead_queue = tenant_api.client.get(
        f"/api/v1/screening/rounds/{title_round['id']}/queue", headers=lead_headers
    )
    reviewer_queue = tenant_api.client.get(
        f"/api/v1/screening/rounds/{title_round['id']}/queue", headers=reviewer_headers
    )
    assert lead_queue.status_code == reviewer_queue.status_code == 200
    assert all(
        item["own_decision"] is None and item["outcome"] is None for item in lead_queue.json()
    )
    assert all(
        item["own_decision"] is None and item["outcome"] is None for item in reviewer_queue.json()
    )

    lead_progress_assignment = assignments[(str(progressed_article["id"]), tenant_api.ids.lead_a)]
    lead_decision = tenant_api.client.post(
        f"/api/v1/screening/assignments/{lead_progress_assignment['id']}/decision",
        headers=lead_headers,
        json={"decision": "INCLUDE"},
    )
    assert lead_decision.status_code == 200
    lead_queue_after = tenant_api.client.get(
        f"/api/v1/screening/rounds/{title_round['id']}/queue", headers=lead_headers
    ).json()
    lead_progress_item = next(
        item for item in lead_queue_after if item["article_id"] == progressed_article["id"]
    )
    assert lead_progress_item["own_decision"] == "INCLUDE"
    assert lead_progress_item["outcome"] is None

    reviewer_progress_assignment = assignments[
        (str(progressed_article["id"]), tenant_api.ids.reviewer_a)
    ]
    disagreement = tenant_api.client.post(
        f"/api/v1/screening/assignments/{reviewer_progress_assignment['id']}/decision",
        headers=reviewer_headers,
        json={"decision": "EXCLUDE", "exclusion_reason": "Population mismatch"},
    )
    assert disagreement.status_code == 200

    for reviewer_id, headers in (
        (tenant_api.ids.lead_a, lead_headers),
        (tenant_api.ids.reviewer_a, reviewer_headers),
    ):
        assignment = assignments[(str(excluded_article["id"]), reviewer_id)]
        response = tenant_api.client.post(
            f"/api/v1/screening/assignments/{assignment['id']}/decision",
            headers=headers,
            json={"decision": "EXCLUDE", "exclusion_reason": "Wrong intervention"},
        )
        assert response.status_code == 200, response.text

    premature_close = tenant_api.client.post(
        f"/api/v1/screening/rounds/{title_round['id']}/close", headers=lead_headers
    )
    assert premature_close.status_code == 409

    outcomes = tenant_api.client.get(
        f"/api/v1/screening/rounds/{title_round['id']}/outcomes", headers=lead_headers
    )
    assert outcomes.status_code == 200
    outcome_by_article = {item["article_id"]: item for item in outcomes.json()}
    assert outcome_by_article[progressed_article["id"]]["outcome"] == "CONFLICT"
    assert outcome_by_article[excluded_article["id"]]["outcome"] == "EXCLUDE"
    adjudication = tenant_api.client.post(
        f"/api/v1/screening/outcomes/{outcome_by_article[progressed_article['id']]['id']}/adjudication",
        headers=lead_headers,
        json={"decision": "INCLUDE", "reason": "Protocol population is eligible"},
    )
    assert adjudication.status_code == 200

    closed = tenant_api.client.post(
        f"/api/v1/screening/rounds/{title_round['id']}/close", headers=lead_headers
    )
    assert closed.status_code == 200
    assert closed.json()["state"] == "CLOSED"
    progression_payload = {"target_round_id": full_text_round["id"]}
    first_progression = tenant_api.client.post(
        f"/api/v1/screening/rounds/{title_round['id']}/progressions",
        headers=lead_headers,
        json=progression_payload,
    )
    replay = tenant_api.client.post(
        f"/api/v1/screening/rounds/{title_round['id']}/progressions",
        headers=lead_headers,
        json=progression_payload,
    )
    assert first_progression.status_code == replay.status_code == 201
    assert first_progression.json() == replay.json()
    assert [item["article_id"] for item in first_progression.json()] == [progressed_article["id"]]
    audit = tenant_api.client.get(
        f"/api/v1/provenance/reviews/{tenant_api.ids.assigned_review}/audit",
        headers=lead_headers,
    )
    assert audit.status_code == 200
    audited_entities = {event["entity_type"] for event in audit.json()}
    assert {
        "screening_assignment",
        "screening_decision",
        "screening_outcome",
        "screening_adjudication",
        "screening_progression",
    } <= audited_entities


def test_screening_enforces_decision_role_ownership_and_tenant_boundaries(
    tenant_api: TenantApi,
) -> None:
    article = _import_screening_fixture(tenant_api)[0]
    round_record = _create_screening_round(
        tenant_api, name="Security boundary", stage="TITLE_ABSTRACT"
    )
    assignment = _assign_screening_article(
        tenant_api,
        round_id=round_record["id"],
        article_id=article["id"],
        reviewer_id=tenant_api.ids.reviewer_a,
    )
    viewer_headers = tenant_api.headers(tenant_api.ids.viewer_a, tenant_api.ids.organization_a)
    reviewer_headers = tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a)
    foreign_headers = tenant_api.headers(tenant_api.ids.owner_b, tenant_api.ids.organization_b)

    assert (
        tenant_api.client.get(
            f"/api/v1/screening/rounds/{round_record['id']}/queue", headers=viewer_headers
        ).status_code
        == 403
    )
    assert (
        tenant_api.client.post(
            f"/api/v1/screening/assignments/{assignment['id']}/decision",
            headers=tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
            json={"decision": "INCLUDE"},
        ).status_code
        == 404
    )
    assert (
        tenant_api.client.post(
            f"/api/v1/screening/assignments/{assignment['id']}/decision",
            headers=foreign_headers,
            json={"decision": "INCLUDE"},
        ).status_code
        == 404
    )
    assert (
        tenant_api.client.get(
            f"/api/v1/screening/rounds/{round_record['id']}/queue", headers=foreign_headers
        ).status_code
        == 404
    )
    invalid_exclusion = tenant_api.client.post(
        f"/api/v1/screening/assignments/{assignment['id']}/decision",
        headers=reviewer_headers,
        json={"decision": "EXCLUDE"},
    )
    assert invalid_exclusion.status_code == 409
    accepted = tenant_api.client.post(
        f"/api/v1/screening/assignments/{assignment['id']}/decision",
        headers=reviewer_headers,
        json={"decision": "INCLUDE"},
    )
    replay = tenant_api.client.post(
        f"/api/v1/screening/assignments/{assignment['id']}/decision",
        headers=reviewer_headers,
        json={"decision": "INCLUDE"},
    )
    assert accepted.status_code == 200
    assert replay.status_code == 409
    assert (
        tenant_api.client.get(
            f"/api/v1/screening/rounds/{round_record['id']}/outcomes",
            headers=reviewer_headers,
        ).status_code
        == 403
    )


def test_screening_rejects_only_the_suppressed_confirmed_duplicate(
    tenant_api: TenantApi,
) -> None:
    _import_dedup_fixture(tenant_api)
    reviewer_headers = tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a)
    run = tenant_api.client.post(
        f"/api/v1/deduplication/reviews/{tenant_api.ids.assigned_review}/runs",
        headers=reviewer_headers,
    )
    assert run.status_code == 201
    candidate = tenant_api.client.get(
        f"/api/v1/deduplication/reviews/{tenant_api.ids.assigned_review}/candidates",
        headers=reviewer_headers,
    ).json()[0]
    retained_id = candidate["left_article_id"]
    suppressed_id = candidate["right_article_id"]
    decision = tenant_api.client.post(
        f"/api/v1/deduplication/candidates/{candidate['id']}/decision",
        headers=reviewer_headers,
        json={
            "decision": "CONFIRMED_DUPLICATE",
            "retained_article_id": retained_id,
            "reason": "Same DOI",
        },
    )
    assert decision.status_code == 200
    round_record = _create_screening_round(
        tenant_api, name="Deduplicated queue", stage="TITLE_ABSTRACT"
    )
    retained = tenant_api.client.post(
        f"/api/v1/screening/rounds/{round_record['id']}/assignments",
        headers=tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
        json={"article_id": retained_id, "reviewer_user_id": str(tenant_api.ids.reviewer_a)},
    )
    suppressed = tenant_api.client.post(
        f"/api/v1/screening/rounds/{round_record['id']}/assignments",
        headers=tenant_api.headers(tenant_api.ids.lead_a, tenant_api.ids.organization_a),
        json={"article_id": suppressed_id, "reviewer_user_id": str(tenant_api.ids.reviewer_a)},
    )
    assert retained.status_code == 201
    assert suppressed.status_code == 409
