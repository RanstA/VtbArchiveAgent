import pytest

from evals.retrieval.evaluator import (
    RetrievalEvalCase,
    evaluate_ranked_ids,
    summarize_results,
)


def test_retrieval_eval_hit_at_1():
    case = RetrievalEvalCase(
        case_id="cat",
        query="聊过猫吗",
        expected_event_ids=[
            "cat-event",
        ],
    )

    result = evaluate_ranked_ids(
        case,
        [
            "cat-event",
            "game-event",
        ],
    )

    assert result.hit_at_1 is True
    assert result.hit_at_3 is True
    assert result.reciprocal_rank == 1.0


def test_retrieval_eval_mrr_for_rank_2():
    case = RetrievalEvalCase(
        case_id="cat",
        query="聊过猫吗",
        expected_event_ids=[
            "cat-event",
        ],
    )

    result = evaluate_ranked_ids(
        case,
        [
            "game-event",
            "cat-event",
        ],
    )

    assert result.hit_at_1 is False
    assert result.hit_at_3 is True

    assert result.reciprocal_rank == (
        pytest.approx(0.5)
    )


def test_retrieval_eval_miss():
    case = RetrievalEvalCase(
        case_id="cat",
        query="聊过猫吗",
        expected_event_ids=[
            "cat-event",
        ],
    )

    result = evaluate_ranked_ids(
        case,
        [
            "game-event",
        ],
    )

    assert result.hit_at_1 is False
    assert result.hit_at_3 is False
    assert result.reciprocal_rank == 0.0


def test_retrieval_eval_summary():
    case = RetrievalEvalCase(
        case_id="cat",
        query="聊过猫吗",
        expected_event_ids=[
            "cat-event",
        ],
    )

    first = evaluate_ranked_ids(
        case,
        ["cat-event"],
    )

    second = evaluate_ranked_ids(
        case,
        [
            "game-event",
            "cat-event",
        ],
    )

    summary = summarize_results(
        [
            first,
            second,
        ]
    )

    assert summary.case_count == 2
    assert summary.hit_at_1 == 0.5
    assert summary.hit_at_3 == 1.0
    assert summary.mrr == pytest.approx(
        0.75
    )