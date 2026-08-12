"""Import all SQLAlchemy mappings so metadata and Alembic see every table."""

from backend.app.analysis.persistence import (
    AnalysisArtifactRecord,
    AnalysisSetEstimateRecord,
    AnalysisSetRecord,
    AnalysisSpecificationRecord,
    AnalysisSpecificationVersionRecord,
    MetaAnalysisRunRecord,
    MetaAnalysisSensitivityRecord,
    MetaAnalysisStudyWeightRecord,
)
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
from backend.app.exports.persistence import ExportArtifactRecord
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
from backend.app.outcomes.persistence import (
    AnalysisReadinessSnapshotRecord,
    EffectEstimateRecord,
    EffectEstimateSourceRecord,
    MeasurementScaleRecord,
    OutcomeDefinitionRecord,
    OutcomeDefinitionVersionRecord,
    OutcomeMappingRecord,
    SynthesisCandidateEstimateRecord,
    SynthesisCandidateSetRecord,
    TimepointWindowRecord,
    UnitDefinitionRecord,
)
from backend.app.prisma.persistence import PrismaSnapshotRecord
from backend.app.protocols.persistence import ProtocolDecisionRecord, ProtocolVersionRecord
from backend.app.provenance.persistence import (
    AIRunRecord,
    AuditEventRecord,
    PromptVersionRecord,
    ScientificProvenanceRecord,
)
from backend.app.reviews.persistence import ReviewMembershipRecord, ReviewRecord
from backend.app.risk_of_bias.persistence import (
    RiskOfBiasAdjudicationRecord,
    RiskOfBiasAnswerRecord,
    RiskOfBiasAssessmentRecord,
    RiskOfBiasComparisonRecord,
    RiskOfBiasDomainJudgmentRecord,
    RiskOfBiasInstrumentDecisionRecord,
    RiskOfBiasInstrumentRecord,
    RiskOfBiasInstrumentVersionRecord,
)
from backend.app.screening.persistence import (
    ScreeningAdjudicationRecord,
    ScreeningAssignmentRecord,
    ScreeningDecisionRecord,
    ScreeningOutcomeRecord,
    ScreeningProgressionRecord,
    ScreeningRoundRecord,
)
from backend.app.search.execution_persistence import (
    IdentificationSourceRecord,
    SearchExecutionArtifactRecord,
    SearchExecutionCitationLinkRecord,
    SearchExecutionEventRecord,
    SearchExecutionRecord,
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
    "AnalysisArtifactRecord",
    "AnalysisReadinessSnapshotRecord",
    "AnalysisSetEstimateRecord",
    "AnalysisSetRecord",
    "AnalysisSpecificationRecord",
    "AnalysisSpecificationVersionRecord",
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
    "EffectEstimateRecord",
    "EffectEstimateSourceRecord",
    "ExportArtifactRecord",
    "ExtractionConflictRecord",
    "ExtractionRunRecord",
    "ExtractionSchemaRecord",
    "ExtractionSchemaVersionRecord",
    "ExtractionValueRecord",
    "ExtractionVerificationRecord",
    "FullTextCriterionJudgmentRecord",
    "FullTextScreeningRecord",
    "HumanCheckpointRecord",
    "IdentificationSourceRecord",
    "JobEventRecord",
    "LocalCredentialRecord",
    "MeasurementScaleRecord",
    "MembershipRecord",
    "MetaAnalysisRunRecord",
    "MetaAnalysisSensitivityRecord",
    "MetaAnalysisStudyWeightRecord",
    "OrganizationRecord",
    "OutcomeDefinitionRecord",
    "OutcomeDefinitionVersionRecord",
    "OutcomeMappingRecord",
    "PrismaSnapshotRecord",
    "PromptVersionRecord",
    "ProtocolDecisionRecord",
    "ProtocolVersionRecord",
    "ReviewMembershipRecord",
    "ReviewRecord",
    "RiskOfBiasAdjudicationRecord",
    "RiskOfBiasAnswerRecord",
    "RiskOfBiasAssessmentRecord",
    "RiskOfBiasComparisonRecord",
    "RiskOfBiasDomainJudgmentRecord",
    "RiskOfBiasInstrumentDecisionRecord",
    "RiskOfBiasInstrumentRecord",
    "RiskOfBiasInstrumentVersionRecord",
    "ScientificProvenanceRecord",
    "ScreeningAdjudicationRecord",
    "ScreeningAssignmentRecord",
    "ScreeningDecisionRecord",
    "ScreeningOutcomeRecord",
    "ScreeningProgressionRecord",
    "ScreeningRoundRecord",
    "SearchExecutionArtifactRecord",
    "SearchExecutionCitationLinkRecord",
    "SearchExecutionEventRecord",
    "SearchExecutionRecord",
    "SearchStrategyVersionRecord",
    "SearchTranslationRecord",
    "StudyArticleLinkRecord",
    "StudyRecord",
    "SynthesisCandidateEstimateRecord",
    "SynthesisCandidateSetRecord",
    "TimepointWindowRecord",
    "UnitDefinitionRecord",
    "UserRecord",
    "WorkflowJobRecord",
    "WorkflowRunRecord",
]
