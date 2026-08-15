from backend.app.ai.service import AIExecutionService


def test_search_demonstration_rejects_forged_evidence_references() -> None:
    errors = AIExecutionService._validate_output(
        {
            "query": "q",
            "rationale": "r",
            "evidence_references": [{"study_id": "00000000-0000-0000-0000-000000000001"}],
            "model_reported_confidence": None,
            "abstention": "NEEDS_HUMAN_REVIEW",
        }
    )
    assert "UNSUPPORTED_EVIDENCE_REFERENCE" in {item["code"] for item in errors}
