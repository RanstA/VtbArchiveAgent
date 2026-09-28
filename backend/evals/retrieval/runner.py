from dataclasses import dataclass

from app.retrieval.bm25 import (
    BM25EventRetriever,
)
from app.retrieval.rrf import (
    rrf_fuse,
)
from app.retrieval.vector import (
    VectorEventRetriever,
)

from evals.retrieval.evaluator import (
    RetrievalEvalCase,
    RetrievalEvalResult,
    evaluate_ranked_ids,
)


@dataclass(
    frozen=True
)
class RetrievalComparisonResult:
    case_id: str

    bm25: RetrievalEvalResult
    vector: RetrievalEvalResult
    rrf: RetrievalEvalResult


def evaluate_retrievers(
    *,
    case: RetrievalEvalCase,
    bm25_retriever: BM25EventRetriever,
    vector_retriever: VectorEventRetriever,
    query_embedding: list[float],
    top_k: int = 5,
) -> RetrievalComparisonResult:
    bm25_results = (
        bm25_retriever.search(
            case.query,
            top_k=top_k,
        )
    )

    vector_results = (
        vector_retriever.search(
            query_embedding,
            top_k=top_k,
        )
    )

    rrf_results = rrf_fuse(
        bm25_results,
        vector_results,
        top_k=top_k,
    )

    bm25_eval = evaluate_ranked_ids(
        case,
        [
            result.event.id
            for result in bm25_results
        ],
    )

    vector_eval = evaluate_ranked_ids(
        case,
        [
            result.event.id
            for result in vector_results
        ],
    )

    rrf_eval = evaluate_ranked_ids(
        case,
        [
            result.event.id
            for result in rrf_results
        ],
    )

    return RetrievalComparisonResult(
        case_id=case.case_id,
        bm25=bm25_eval,
        vector=vector_eval,
        rrf=rrf_eval,
    )