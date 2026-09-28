from app.domain.event import Event

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
    evaluate_retrievers,
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


def test_compare_bm25_vector_and_rrf():
    cat = make_event(
        event_id="cat-event",
        semantic_text=("观众讨论猫和猫咪"),
    )

    pet = make_event(
        event_id="pet-event",
        semantic_text=("观众讨论宠物饲养"),
    )

    game = make_event(
        event_id="game-event",
        semantic_text=("观众讨论游戏失败"),
    )

    events = [
        cat,
        pet,
        game,
    ]

    bm25_retriever = BM25EventRetriever(events)

    vector_retriever = VectorEventRetriever(
        events=events,
        embeddings=[
            # cat-event
            [0.9, 0.1],
            # pet-event
            [1.0, 0.0],
            # game-event
            [0.0, 1.0],
        ],
    )

    case = RetrievalEvalCase(
        case_id="pet-query",
        query="之前聊过猫吗",
        expected_event_ids=[
            "cat-event",
            "pet-event",
        ],
    )

    comparison = evaluate_retrievers(
        case=case,
        bm25_retriever=(bm25_retriever),
        vector_retriever=(vector_retriever),
        query_embedding=[
            1.0,
            0.0,
        ],
        top_k=3,
    )

    assert comparison.bm25.hit_at_1 is True

    assert comparison.vector.hit_at_1 is True

    assert comparison.rrf.hit_at_1 is True

    assert comparison.rrf.reciprocal_rank == 1.0
