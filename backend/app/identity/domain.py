from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class OrganizationRole(StrEnum):
    OWNER = "owner"
    ADMINISTRATOR = "administrator"
    LEAD_REVIEWER = "lead_reviewer"
    REVIEWER = "reviewer"
    STATISTICIAN = "statistician"
    VIEWER = "viewer"


class Permission(StrEnum):
    MANAGE_ORGANIZATION = "manage_organization"
    CREATE_REVIEW = "create_review"
    VIEW_ALL_REVIEWS = "view_all_reviews"
    UPDATE_ASSIGNED_REVIEW = "update_assigned_review"
    MANAGE_REVIEW_ACCESS = "manage_review_access"
    TRANSFER_REVIEW_OWNERSHIP = "transfer_review_ownership"
    RECORD_PROVENANCE = "record_provenance"
    MANAGE_PROTOCOL = "manage_protocol"
    MANAGE_SEARCH = "manage_search"
    IMPORT_CITATIONS = "import_citations"
    MANAGE_DEDUPLICATION = "manage_deduplication"
    MANAGE_SCREENING = "manage_screening"
    SCREEN_ARTICLES = "screen_articles"
    MANAGE_DOCUMENTS = "manage_documents"
    MANAGE_STUDIES = "manage_studies"
    MANAGE_EXTRACTION_SCHEMA = "manage_extraction_schema"
    PERFORM_EXTRACTION = "perform_extraction"
    ADJUDICATE_EXTRACTION = "adjudicate_extraction"
    MANAGE_ROB_INSTRUMENT = "manage_rob_instrument"
    PERFORM_ROB_ASSESSMENT = "perform_rob_assessment"
    ADJUDICATE_ROB = "adjudicate_rob"
    MANAGE_OUTCOMES = "manage_outcomes"
    HARMONIZE_OUTCOMES = "harmonize_outcomes"
    PREPARE_SYNTHESIS = "prepare_synthesis"
    MANAGE_ANALYSIS = "manage_analysis"
    RUN_ANALYSIS = "run_analysis"
    MANAGE_CERTAINTY_FRAMEWORK = "manage_certainty_framework"
    ASSESS_CERTAINTY = "assess_certainty"
    ADJUDICATE_CERTAINTY = "adjudicate_certainty"
    EXPORT_REVIEW = "export_review"
    GENERATE_REPORT = "generate_report"


ROLE_PERMISSIONS: dict[OrganizationRole, frozenset[Permission]] = {
    OrganizationRole.OWNER: frozenset(Permission),
    OrganizationRole.ADMINISTRATOR: frozenset(Permission),
    OrganizationRole.LEAD_REVIEWER: frozenset(
        {
            Permission.CREATE_REVIEW,
            Permission.UPDATE_ASSIGNED_REVIEW,
            Permission.MANAGE_REVIEW_ACCESS,
            Permission.RECORD_PROVENANCE,
            Permission.MANAGE_PROTOCOL,
            Permission.MANAGE_SEARCH,
            Permission.IMPORT_CITATIONS,
            Permission.MANAGE_DEDUPLICATION,
            Permission.MANAGE_SCREENING,
            Permission.SCREEN_ARTICLES,
            Permission.MANAGE_DOCUMENTS,
            Permission.MANAGE_STUDIES,
            Permission.MANAGE_EXTRACTION_SCHEMA,
            Permission.PERFORM_EXTRACTION,
            Permission.ADJUDICATE_EXTRACTION,
            Permission.MANAGE_ROB_INSTRUMENT,
            Permission.PERFORM_ROB_ASSESSMENT,
            Permission.ADJUDICATE_ROB,
            Permission.MANAGE_OUTCOMES,
            Permission.HARMONIZE_OUTCOMES,
            Permission.PREPARE_SYNTHESIS,
            Permission.MANAGE_ANALYSIS,
            Permission.RUN_ANALYSIS,
            Permission.MANAGE_CERTAINTY_FRAMEWORK,
            Permission.ASSESS_CERTAINTY,
            Permission.ADJUDICATE_CERTAINTY,
            Permission.EXPORT_REVIEW,
            Permission.GENERATE_REPORT,
        }
    ),
    OrganizationRole.REVIEWER: frozenset(
        {
            Permission.UPDATE_ASSIGNED_REVIEW,
            Permission.RECORD_PROVENANCE,
            Permission.IMPORT_CITATIONS,
            Permission.MANAGE_DEDUPLICATION,
            Permission.SCREEN_ARTICLES,
            Permission.MANAGE_DOCUMENTS,
            Permission.MANAGE_STUDIES,
            Permission.MANAGE_EXTRACTION_SCHEMA,
            Permission.PERFORM_EXTRACTION,
            Permission.ADJUDICATE_EXTRACTION,
            Permission.PERFORM_ROB_ASSESSMENT,
            Permission.HARMONIZE_OUTCOMES,
            Permission.ASSESS_CERTAINTY,
        }
    ),
    OrganizationRole.STATISTICIAN: frozenset(
        {
            Permission.RECORD_PROVENANCE,
            Permission.MANAGE_OUTCOMES,
            Permission.HARMONIZE_OUTCOMES,
            Permission.PREPARE_SYNTHESIS,
            Permission.MANAGE_ANALYSIS,
            Permission.RUN_ANALYSIS,
            Permission.ASSESS_CERTAINTY,
        }
    ),
    OrganizationRole.VIEWER: frozenset(),
}


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    user_id: UUID


@dataclass(frozen=True, slots=True)
class ActorContext:
    user_id: UUID
    organization_id: UUID
    membership_id: UUID
    role: OrganizationRole

    def has_permission(self, permission: Permission) -> bool:
        return permission in ROLE_PERMISSIONS[self.role]


@dataclass(frozen=True, slots=True)
class LoginRecord:
    user_id: UUID
    password_hash: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class OrganizationSummary:
    id: UUID
    name: str
    slug: str
