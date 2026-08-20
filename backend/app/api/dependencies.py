from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import Settings
from backend.app.core.errors import AuthenticationError, InvalidOrganizationContextError
from backend.app.db.session import get_db_session
from backend.app.identity.domain import ActorContext
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.identity.security import LocalTokenAuthenticationProvider
from backend.app.identity.service import ActorContextService
from backend.app.malware.contracts import MalwareScanner
from backend.app.malware.factory import build_malware_scanner
from backend.app.services.health import HealthService, get_health_service
from backend.app.storage.contracts import VerifiedObjectStorageProvider
from backend.app.storage.local import LocalFileStorageProvider

HealthServiceDependency = Annotated[HealthService, Depends(get_health_service)]
DbSessionDependency = Annotated[AsyncSession, Depends(get_db_session)]


def get_request_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


SettingsDependency = Annotated[Settings, Depends(get_request_settings)]


def get_object_storage(settings: SettingsDependency) -> VerifiedObjectStorageProvider:
    if settings.object_storage_provider != "local":
        raise RuntimeError("the configured object storage provider is not installed")
    return LocalFileStorageProvider(settings.local_storage_path)


ObjectStorageDependency = Annotated[VerifiedObjectStorageProvider, Depends(get_object_storage)]


def get_malware_scanner(settings: SettingsDependency) -> MalwareScanner:
    return build_malware_scanner(settings)


MalwareScannerDependency = Annotated[MalwareScanner, Depends(get_malware_scanner)]


def build_authentication_provider(settings: Settings) -> LocalTokenAuthenticationProvider:
    if settings.authentication_provider != "local":
        raise RuntimeError("the configured production authentication provider is not installed")
    return LocalTokenAuthenticationProvider(
        secret=settings.local_auth_secret.get_secret_value(),
        token_ttl_seconds=settings.local_auth_token_ttl_seconds,
    )


async def get_actor_context(
    session: DbSessionDependency,
    settings: SettingsDependency,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    organization_header: Annotated[str | None, Header(alias="X-Organization-ID")] = None,
) -> ActorContext:
    if authorization is None or not authorization.startswith("Bearer "):
        raise AuthenticationError("bearer authentication is required")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise AuthenticationError("bearer authentication is required")
    if organization_header is None:
        raise InvalidOrganizationContextError("X-Organization-ID is required")
    try:
        organization_id = UUID(organization_header)
    except ValueError:
        raise InvalidOrganizationContextError("X-Organization-ID is invalid") from None

    identity = build_authentication_provider(settings).authenticate(token)
    repository = SqlAlchemyIdentityRepository(session)
    return await ActorContextService(repository).resolve(identity.user_id, organization_id)


ActorContextDependency = Annotated[ActorContext, Depends(get_actor_context)]
