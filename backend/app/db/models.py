"""Import all SQLAlchemy mappings so metadata and Alembic see every table."""

from backend.app.identity.persistence import (
    LocalCredentialRecord,
    MembershipRecord,
    OrganizationRecord,
    UserRecord,
)
from backend.app.reviews.persistence import ReviewMembershipRecord, ReviewRecord

__all__ = [
    "LocalCredentialRecord",
    "MembershipRecord",
    "OrganizationRecord",
    "ReviewMembershipRecord",
    "ReviewRecord",
    "UserRecord",
]
