from backend.app.ai.domain import AITaskType
from backend.app.ai.evaluation import AIEvaluationCase, evaluate_exact_match


def test_versioned_golden_evaluation_case_is_hashable_and_measurable() -> None:
    expected = {"query": "aspirin AND randomized", "abstention": None}
    case = AIEvaluationCase.create(
        key="search-query-basic",
        version=1,
        task_type=AITaskType.SEARCH_QUERY_SUGGESTION,
        input_data={"query": "aspirin", "objective": "find trials"},
        expected_output=expected,
    )
    assert len(case.content_hash) == 64
    assert evaluate_exact_match(case, expected).exact_match is True
    assert evaluate_exact_match(case, {**expected, "query": "different"}).exact_match is False
