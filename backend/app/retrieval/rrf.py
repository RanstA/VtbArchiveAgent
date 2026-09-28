from dataclasses import dataclass

from app.domain.event import Event
from app.retrieval.bm25 import (
    BM25SearchResult,
)
from app.retrieval.vector import (
    VectorSearchResult,
)


DEFAULT_RRF_K = 60


@dataclass(
    frozen=True
)
class RRFSearchResult:
    event: Event
    score: float

    bm25_rank: int | None = None
    vector_rank: int | None = None


def rrf_fuse(
    bm25_results: list[BM25SearchResult],
    vector_results: list[VectorSearchResult],
    *,
    top_k: int = 8,
    rrf_k: int = DEFAULT_RRF_K,
) -> list[RRFSearchResult]:
    if top_k < 1:
        raise ValueError(
            "top_k must be >= 1"
        )

    if rrf_k < 1:
        raise ValueError(
            "rrf_k must be >= 1"
        )

    events: dict[str, Event] = {}
    scores: dict[str, float] = {}

    bm25_ranks: dict[str, int] = {}
    vector_ranks: dict[str, int] = {}

    for rank, result in enumerate(
        bm25_results,
        start=1,
    ):
        event_id = result.event.id

        events[event_id] = result.event
        bm25_ranks[event_id] = rank

        scores[event_id] = (
            scores.get(
                event_id,
                0.0,
            )
            + 1.0 / (
                rrf_k + rank
            )
        )

    for rank, result in enumerate(
        vector_results,
        start=1,
    ):
        event_id = result.event.id

        events[event_id] = result.event
        vector_ranks[event_id] = rank

        scores[event_id] = (
            scores.get(
                event_id,
                0.0,
            )
            + 1.0 / (
                rrf_k + rank
            )
        )

    results = [
        RRFSearchResult(
            event=events[event_id],
            score=score,
            bm25_rank=(
                bm25_ranks.get(
                    event_id
                )
            ),
            vector_rank=(
                vector_ranks.get(
                    event_id
                )
            ),
        )
        for event_id, score
        in scores.items()
    ]

    results.sort(
        key=lambda result: (
            -result.score,
            result.event.id,
        )
    )

    return results[:top_k]