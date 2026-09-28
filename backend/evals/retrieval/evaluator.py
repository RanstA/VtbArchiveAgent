from dataclasses import dataclass


@dataclass(
    frozen=True
)
class RetrievalEvalCase:
    case_id: str
    query: str
    expected_event_ids: list[str]


@dataclass(
    frozen=True
)
class RetrievalEvalResult:
    case_id: str
    query: str

    ranked_event_ids: list[str]

    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool

    reciprocal_rank: float


def evaluate_ranked_ids(
    case: RetrievalEvalCase,
    ranked_event_ids: list[str],
) -> RetrievalEvalResult:
    expected = set(
        case.expected_event_ids
    )

    if not expected:
        raise ValueError(
            "expected_event_ids "
            "must not be empty"
        )

    reciprocal_rank = 0.0

    for rank, event_id in enumerate(
        ranked_event_ids,
        start=1,
    ):
        if event_id in expected:
            reciprocal_rank = (
                1.0 / rank
            )
            break

    return RetrievalEvalResult(
        case_id=case.case_id,
        query=case.query,
        ranked_event_ids=list(
            ranked_event_ids
        ),
        hit_at_1=any(
            event_id in expected
            for event_id
            in ranked_event_ids[:1]
        ),
        hit_at_3=any(
            event_id in expected
            for event_id
            in ranked_event_ids[:3]
        ),
        hit_at_5=any(
            event_id in expected
            for event_id
            in ranked_event_ids[:5]
        ),
        reciprocal_rank=(
            reciprocal_rank
        ),
    )


@dataclass(
    frozen=True
)
class RetrievalEvalSummary:
    case_count: int

    hit_at_1: float
    hit_at_3: float
    hit_at_5: float

    mrr: float


def summarize_results(
    results: list[RetrievalEvalResult],
) -> RetrievalEvalSummary:
    if not results:
        raise ValueError(
            "results must not be empty"
        )

    count = len(results)

    return RetrievalEvalSummary(
        case_count=count,

        hit_at_1=sum(
            result.hit_at_1
            for result in results
        ) / count,

        hit_at_3=sum(
            result.hit_at_3
            for result in results
        ) / count,

        hit_at_5=sum(
            result.hit_at_5
            for result in results
        ) / count,

        mrr=sum(
            result.reciprocal_rank
            for result in results
        ) / count,
    )