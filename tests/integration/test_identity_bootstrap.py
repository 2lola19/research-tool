from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.core.errors import ConflictError
from backend.app.db import models as database_models
from backend.app.db.base import Base
from backend.app.identity.bootstrap import bootstrap_local_identity
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.identity.security import ScryptPasswordHasher


async def test_local_identity_bootstrap_creates_login_and_owner_membership(
    tmp_path: Path,
) -> None:
    _ = database_models
    database_path = tmp_path / "bootstrap.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        result = await bootstrap_local_identity(
            session,
            email="OWNER@EXAMPLE.TEST",
            password="correct horse battery staple",
            display_name="Local Owner",
            organization_name="Local Organization",
            organization_slug="local-organization",
        )

    async with session_factory() as session:
        repository = SqlAlchemyIdentityRepository(session)
        login = await repository.get_login_record("owner@example.test")
        actor = await repository.get_actor_context(result.user_id, result.organization_id)

    assert login is not None
    assert ScryptPasswordHasher().verify_password(
        "correct horse battery staple",
        login.password_hash,
    )
    assert actor is not None
    assert actor.role.value == "owner"

    async with session_factory() as session:
        try:
            await bootstrap_local_identity(
                session,
                email="owner@example.test",
                password="correct horse battery staple",
                display_name="Duplicate Owner",
                organization_name="Another Organization",
                organization_slug="another-organization",
            )
        except ConflictError:
            pass
        else:
            raise AssertionError("duplicate local bootstrap must be rejected")

    await engine.dispose()
