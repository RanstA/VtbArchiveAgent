import pytest

from app.domain.event import Event
from app.retrieval.bm25 import BM25SearchResult
from app.retrieval.rrf import rrf_fuse
from app.retrieval.vector import VectorSearchResult


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


def test_rrf_promotes_event_supported_by_both_retrievers():
    cat = make_event("cat")
    game = make_event("game")
    singing = make_event("singing")

    bm25_results = [
        BM25SearchResult(
            event=cat,
            score=10.0,
        ),
        BM25SearchResult(
            event=game,
            score=9.0,
        ),
        BM25SearchResult(
            event=singing,
            score=8.0,
        ),
    ]

    vector_results = [
        VectorSearchResult(
            event=game,
            score=0.95,
        ),
        VectorSearchResult(
            event=singing,
            score=0.90,
        ),
    ]

    results = rrf_fuse(
        bm25_results,
        vector_results,
        top_k=3,
    )

    assert results[0].event.id == "game"

    assert results[0].bm25_rank == 2
    assert results[0].vector_rank == 1


def test_rrf_keeps_single_source_event():
    cat = make_event("cat")

    results = rrf_fuse(
        bm25_results=[
            BM25SearchResult(
                event=cat,
                score=5.0,
            ),
        ],
        vector_results=[],
    )

    assert len(results) == 1

    assert results[0].event.id == "cat"
    assert results[0].bm25_rank == 1
    assert results[0].vector_rank is None


def test_rrf_respects_top_k():
    events = [
        make_event("a"),
        make_event("b"),
        make_event("c"),
    ]

    bm25_results = [
        BM25SearchResult(
            event=event,
            score=1.0,
        )
        for event in events
    ]

    results = rrf_fuse(
        bm25_results,
        [],
        top_k=2,
    )

    assert len(results) == 2


def test_rrf_rejects_invalid_top_k():
    with pytest.raises(
        ValueError,
        match="top_k must be >= 1",
    ):
        rrf_fuse(
            [],
            [],
            top_k=0,
        )