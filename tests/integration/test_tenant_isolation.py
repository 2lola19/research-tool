from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.api.dependencies import build_authentication_provider
from backend.app.core.config import Settings
from backend.app.db import models as database_models
from backend.app.db.base import Base
from backend.app.db.session import get_db_session
from backend.app.identity.domain import OrganizationRole
from backend.app.identity.persistence import (
    LocalCredentialRecord,
    MembershipRecord,
    OrganizationRecord,
    UserRecord,
)
from backend.app.identity.security import ScryptPasswordHasher
from backend.app.main import create_app
from backend.app.reviews.persistence import ReviewMembershipRecord, ReviewRecord

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
            owner_user_id=users["lead_a"].id,
            created_by_user_id=users["lead_a"].id,
        )
        private_review = ReviewRecord(
            organization_id=organization_a.id,
            title="Private review",
            owner_user_id=users["owner_a"].id,
            created_by_user_id=users["owner_a"].id,
        )
        delegated_review = ReviewRecord(
            organization_id=organization_a.id,
            title="Delegated review",
            owner_user_id=users["owner_a"].id,
            created_by_user_id=users["owner_a"].id,
        )
        organization_b_review = ReviewRecord(
            organization_id=organization_b.id,
            title="Organization B review",
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
    database_path = tmp_path / "tenant.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
        poolclass=NullPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _: object) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")  # type: ignore[attr-defined]

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare() -> TenantIds:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        return await _seed(session_factory)

    ids = asyncio.run(prepare())
    settings = Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{database_path.as_posix()}",
        local_auth_secret="test-local-authentication-secret",
    )
    app = create_app(settings)

    async def override_session() -> object:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    with TestClient(app, raise_server_exceptions=False) as client:
        yield TenantApi(client=client, settings=settings, ids=ids)
    asyncio.run(engine.dispose())


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
        json={"title": "Reviewer update"},
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
        json={"title": "Cross-tenant update"},
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
        json={"title": "Viewer update"},
    )
    assert viewer_update.status_code == 403

    reviewer_create = tenant_api.client.post(
        "/api/v1/reviews",
        headers=tenant_api.headers(tenant_api.ids.reviewer_a, tenant_api.ids.organization_a),
        json={"title": "Unauthorized project"},
    )
    assert reviewer_create.status_code == 403

    statistician_update = tenant_api.client.patch(
        f"/api/v1/reviews/{tenant_api.ids.assigned_review}",
        headers=tenant_api.headers(
            tenant_api.ids.statistician_a,
            tenant_api.ids.organization_a,
        ),
        json={"title": "Statistician update"},
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
