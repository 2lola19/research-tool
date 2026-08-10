"""Import all SQLAlchemy mappings so metadata and Alembic see every table."""

from backend.app.citations.persistence import (
    ArticleRecord,
    CitationImportBatchRecord,
    CitationSourceRecordRow,
)
from backend.app.deduplication.persistence import (
    DeduplicationDecisionRecord,
    DeduplicationRunRecord,
    DuplicateCandidateRecord,
)
from backend.app.identity.persistence import (
    LocalCredentialRecord,
    MembershipRecord,
    OrganizationRecord,
    UserRecord,
)
from backend.app.protocols.persistence import ProtocolDecisionRecord, ProtocolVersionRecord
from backend.app.provenance.persistence import (
    AIRunRecord,
    AuditEventRecord,
    PromptVersionRecord,
    ScientificProvenanceRecord,
)
from backend.app.reviews.persistence import ReviewMembershipRecord, ReviewRecord
from backend.app.screening.persistence import (
    ScreeningAdjudicationRecord,
    ScreeningAssignmentRecord,
    ScreeningDecisionRecord,
    ScreeningOutcomeRecord,
    ScreeningProgressionRecord,
    ScreeningRoundRecord,
)
from backend.app.search.persistence import SearchStrategyVersionRecord, SearchTranslationRecord
from backend.app.workflow.persistence import (
    HumanCheckpointRecord,
    JobEventRecord,
    WorkflowJobRecord,
    WorkflowRunRecord,
)

__all__ = [
    "AIRunRecord",
    "ArticleRecord",
    "AuditEventRecord",
    "CitationImportBatchRecord",
    "CitationSourceRecordRow",
    "DeduplicationDecisionRecord",
    "DeduplicationRunRecord",
    "DuplicateCandidateRecord",
    "HumanCheckpointRecord",
    "JobEventRecord",
    "LocalCredentialRecord",
    "MembershipRecord",
    "OrganizationRecord",
    "PromptVersionRecord",
    "ProtocolDecisionRecord",
    "ProtocolVersionRecord",
    "ReviewMembershipRecord",
    "ReviewRecord",
    "ScientificProvenanceRecord",
    "ScreeningAdjudicationRecord",
    "ScreeningAssignmentRecord",
    "ScreeningDecisionRecord",
    "ScreeningOutcomeRecord",
    "ScreeningProgressionRecord",
    "ScreeningRoundRecord",
    "SearchStrategyVersionRecord",
    "SearchTranslationRecord",
    "UserRecord",
    "WorkflowJobRecord",
    "WorkflowRunRecord",
]
