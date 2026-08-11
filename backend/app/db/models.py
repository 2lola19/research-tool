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
from backend.app.documents.persistence import (
    DocumentBlockRecord,
    DocumentEvidenceLocationRecord,
    DocumentProcessingRunRecord,
    DocumentRecord,
    DocumentWarningRecord,
    FullTextCriterionJudgmentRecord,
    FullTextScreeningRecord,
)
from backend.app.extraction.manual_persistence import ExtractionRunRecord, ExtractionValueRecord
from backend.app.extraction.schema_persistence import (
    ExtractionSchemaRecord,
    ExtractionSchemaVersionRecord,
)
from backend.app.extraction.verification_persistence import (
    ExtractionConflictRecord,
    ExtractionVerificationRecord,
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
from backend.app.studies.persistence import StudyArticleLinkRecord, StudyRecord
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
    "DocumentBlockRecord",
    "DocumentEvidenceLocationRecord",
    "DocumentProcessingRunRecord",
    "DocumentRecord",
    "DocumentWarningRecord",
    "DuplicateCandidateRecord",
    "ExtractionConflictRecord",
    "ExtractionRunRecord",
    "ExtractionSchemaRecord",
    "ExtractionSchemaVersionRecord",
    "ExtractionValueRecord",
    "ExtractionVerificationRecord",
    "FullTextCriterionJudgmentRecord",
    "FullTextScreeningRecord",
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
    "StudyArticleLinkRecord",
    "StudyRecord",
    "UserRecord",
    "WorkflowJobRecord",
    "WorkflowRunRecord",
]
