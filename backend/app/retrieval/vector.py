import math
from dataclasses import dataclass

from app.domain.event import Event


@dataclass(
    frozen=True
)
class VectorSearchResult:
    event: Event
    score: float


def cosine_similarity(
    left: list[float],
    right: list[float],
) -> float:
    if len(left) != len(right):
        raise ValueError(
            "embedding dimensions must match"
        )

    if not left:
        raise ValueError(
            "embeddings must not be empty"
        )

    dot_product = sum(
        a * b
        for a, b in zip(
            left,
            right,
        )
    )

    left_norm = math.sqrt(
        sum(
            value * value
            for value in left
        )
    )

    right_norm = math.sqrt(
        sum(
            value * value
            for value in right
        )
    )

    if (
        left_norm == 0.0
        or right_norm == 0.0
    ):
        return 0.0

    return (
        dot_product
        / (
            left_norm
            * right_norm
        )
    )


class VectorEventRetriever:
    def __init__(
        self,
        events: list[Event],
        embeddings: list[list[float]],
    ) -> None:
        if len(events) != len(embeddings):
            raise ValueError(
                "events and embeddings "
                "must have the same length"
            )

        if embeddings:
            dimension = len(
                embeddings[0]
            )

            if dimension == 0:
                raise ValueError(
                    "embeddings must not be empty"
                )

            if any(
                len(item) != dimension
                for item in embeddings
            ):
                raise ValueError(
                    "all embeddings must "
                    "have the same dimension"
                )

        self.events = list(events)
        self.embeddings = [
            list(item)
            for item in embeddings
        ]

    def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 8,
    ) -> list[VectorSearchResult]:
        if top_k < 1:
            raise ValueError(
                "top_k must be >= 1"
            )

        if not query_embedding:
            raise ValueError(
                "query_embedding must not be empty"
            )

        results = [
            VectorSearchResult(
                event=event,
                score=cosine_similarity(
                    query_embedding,
                    embedding,
                ),
            )
            for event, embedding
            in zip(
                self.events,
                self.embeddings,
            )
        ]

        results.sort(
            key=lambda result: (
                -result.score,
                result.event.id,
            )
        )

        return results[:top_k]