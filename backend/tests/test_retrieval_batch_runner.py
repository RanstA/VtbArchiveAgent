import pytest

from app.domain.event import (
    Event,
)
from app.retrieval.bm25 import (
    BM25EventRetriever,
)
from app.retrieval.vector import (
    VectorEventRetriever,
)

from evals.retrieval.evaluator import (
    RetrievalEvalCase,
)
from evals.retrieval.runner import (
    evaluate_retrieval_cases,
)


def make_event(
    *,
    event_id: str,
    semantic_text: str,
) -> Event:
    return Event(
        id=event_id,
        stream_id="stream-1",
        source_part_ids=[
            "p0",
        ],
        start_ms=0,
        end_ms=30_000,
        anchor_ms=15_000,
        source_highlight_ids=[
            f"highlight-{event_id}",
        ],
        title=event_id,
        summary=semantic_text,
        keywords=[],
        entities=[],
        semantic_text=semantic_text,
        salience_score=0.5,
        segmenter_version="test-v1",
        semanticizer_version="v1",
    )


def make_retrievers():
    cat = make_event(
        event_id="cat-event",
        semantic_text=("观众讨论猫和猫咪"),
    )

    game = make_event(
        event_id="game-event",
        semantic_text=("观众讨论游戏失败"),
    )

    singing = make_event(
        event_id="singing-event",
        semantic_text=("观众讨论唱歌和歌曲"),
    )

    events = [
        cat,
        game,
        singing,
    ]

    bm25 = BM25EventRetriever(events)

    vector = VectorEventRetriever(
        events=events,
        embeddings=[
            # cat
            [1.0, 0.0, 0.0],
            # game
            [0.0, 1.0, 0.0],
            # singing
            [0.0, 0.0, 1.0],
        ],
    )

    return bm25, vector


def test_batch_evaluator_summarizes_all_retrievers():
    bm25, vector = make_retrievers()

    cases = [
        RetrievalEvalCase(
            case_id="cat",
            query="之前聊过猫吗",
            expected_event_ids=[
                "cat-event",
            ],
        ),
        RetrievalEvalCase(
            case_id="game",
            query="哪次讨论过游戏失败",
            expected_event_ids=[
                "game-event",
            ],
        ),
    ]

    result = evaluate_retrieval_cases(
        cases=cases,
        bm25_retriever=bm25,
        vector_retriever=vector,
        query_embeddings={
            "cat": [
                1.0,
                0.0,
                0.0,
            ],
            "game": [
                0.0,
                1.0,
                0.0,
            ],
        },
        top_k=3,
    )

    assert len(result.comparisons) == 2

    assert result.bm25.case_count == 2

    assert result.vector.case_count == 2

    assert result.rrf.case_count == 2

    assert result.bm25.hit_at_1 == pytest.approx(1.0)

    assert result.vector.hit_at_1 == pytest.approx(1.0)

    assert result.rrf.hit_at_1 == pytest.approx(1.0)

    assert result.rrf.mrr == pytest.approx(1.0)


def test_batch_evaluator_rejects_empty_cases():
    bm25, vector = make_retrievers()

    with pytest.raises(
        ValueError,
        match=("cases must not be empty"),
    ):
        evaluate_retrieval_cases(
            cases=[],
            bm25_retriever=bm25,
            vector_retriever=vector,
            query_embeddings={},
        )


def test_batch_evaluator_requires_query_embedding():
    bm25, vector = make_retrievers()

    cases = [
        RetrievalEvalCase(
            case_id="cat",
            query="聊过猫吗",
            expected_event_ids=[
                "cat-event",
            ],
        ),
    ]

    with pytest.raises(
        ValueError,
        match=("missing query embedding " "for case: cat"),
    ):
        evaluate_retrieval_cases(
            cases=cases,
            bm25_retriever=bm25,
            vector_retriever=vector,
            query_embeddings={},
        )
