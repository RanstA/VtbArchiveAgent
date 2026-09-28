import pytest

from app.domain.event import Event
from app.retrieval.vector import (
    VectorEventRetriever,
    cosine_similarity,
)


def make_event(
    event_id: str,
) -> Event:
    return Event(
        id=event_id,
        stream_id="stream-1",
        part_id="part-1",
        start_ms=0,
        end_ms=30_000,
        peak_ms=15_000,
        source_highlight_ids=[
            f"highlight-{event_id}",
        ],
        title=event_id,
        summary=event_id,
        keywords=[],
        entities=[],
        semantic_text=event_id,
        semanticizer_version="v1",
    )


def test_cosine_similarity():
    assert cosine_similarity(
        [1.0, 0.0],
        [1.0, 0.0],
    ) == pytest.approx(1.0)

    assert cosine_similarity(
        [1.0, 0.0],
        [0.0, 1.0],
    ) == pytest.approx(0.0)


def test_vector_retriever_ranks_most_similar_first():
    events = [
        make_event("cat"),
        make_event("game"),
        make_event("singing"),
    ]

    embeddings = [
        [1.0, 0.0],
        [0.0, 1.0],
        [-1.0, 0.0],
    ]

    retriever = VectorEventRetriever(
        events=events,
        embeddings=embeddings,
    )

    results = retriever.search(
        [0.9, 0.1],
        top_k=3,
    )

    assert results[0].event.id == "cat"
    assert (
        results[0].score
        > results[1].score
    )


def test_vector_retriever_respects_top_k():
    events = [
        make_event("event-1"),
        make_event("event-2"),
    ]

    retriever = VectorEventRetriever(
        events=events,
        embeddings=[
            [1.0, 0.0],
            [0.5, 0.5],
        ],
    )

    results = retriever.search(
        [1.0, 0.0],
        top_k=1,
    )

    assert len(results) == 1


def test_vector_retriever_rejects_dimension_mismatch():
    retriever = VectorEventRetriever(
        events=[
            make_event("event-1"),
        ],
        embeddings=[
            [1.0, 0.0],
        ],
    )

    with pytest.raises(
        ValueError,
        match="embedding dimensions must match",
    ):
        retriever.search(
            [1.0, 0.0, 0.0],
        )