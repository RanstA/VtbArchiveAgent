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
    RetrievalEvalSummary,
    evaluate_ranked_ids,
    summarize_results,
)


@dataclass(frozen=True)
class RetrievalComparisonResult:
    case_id: str

    bm25: RetrievalEvalResult
    vector: RetrievalEvalResult
    rrf: RetrievalEvalResult


@dataclass(frozen=True)
class RetrievalBatchResult:
    """
    多个 Retrieval Eval Case
    的整体比较结果。
    """

    comparisons: list[RetrievalComparisonResult]

    bm25: RetrievalEvalSummary
    vector: RetrievalEvalSummary
    rrf: RetrievalEvalSummary


def evaluate_retrievers(
    *,
    case: RetrievalEvalCase,
    bm25_retriever: BM25EventRetriever,
    vector_retriever: VectorEventRetriever,
    query_embedding: list[float],
    top_k: int = 5,
) -> RetrievalComparisonResult:
    bm25_results = bm25_retriever.search(
        case.query,
        top_k=top_k,
    )

    vector_results = vector_retriever.search(
        query_embedding,
        top_k=top_k,
    )

    rrf_results = rrf_fuse(
        bm25_results,
        vector_results,
        top_k=top_k,
    )

    bm25_eval = evaluate_ranked_ids(
        case,
        [result.event.id for result in bm25_results],
    )

    vector_eval = evaluate_ranked_ids(
        case,
        [result.event.id for result in vector_results],
    )

    rrf_eval = evaluate_ranked_ids(
        case,
        [result.event.id for result in rrf_results],
    )

    return RetrievalComparisonResult(
        case_id=case.case_id,
        bm25=bm25_eval,
        vector=vector_eval,
        rrf=rrf_eval,
    )


def evaluate_retrieval_cases(
    *,
    cases: list[RetrievalEvalCase],
    bm25_retriever: BM25EventRetriever,
    vector_retriever: VectorEventRetriever,
    query_embeddings: dict[
        str,
        list[float],
    ],
    top_k: int = 5,
) -> RetrievalBatchResult:
    """
    批量评估 BM25 / Vector / RRF。

    query_embeddings 使用 case_id
    作为 key，使 Eval 数据与向量生成逻辑解耦。
    """

    if not cases:
        raise ValueError("cases must not be empty")

    comparisons: list[RetrievalComparisonResult] = []

    for case in cases:
        if case.case_id not in query_embeddings:
            raise ValueError("missing query embedding " f"for case: {case.case_id}")

        comparison = evaluate_retrievers(
            case=case,
            bm25_retriever=(bm25_retriever),
            vector_retriever=(vector_retriever),
            query_embedding=(query_embeddings[case.case_id]),
            top_k=top_k,
        )

        comparisons.append(comparison)

    bm25_summary = summarize_results([comparison.bm25 for comparison in comparisons])

    vector_summary = summarize_results(
        [comparison.vector for comparison in comparisons]
    )

    rrf_summary = summarize_results([comparison.rrf for comparison in comparisons])

    return RetrievalBatchResult(
        comparisons=comparisons,
        bm25=bm25_summary,
        vector=vector_summary,
        rrf=rrf_summary,
    )
