import json
from pathlib import Path

from evals.retrieval.evaluator import (
    RetrievalEvalCase,
)


class RetrievalEvalDatasetError(RuntimeError):
    pass


def load_retrieval_eval_cases(
    path: str | Path,
) -> list[RetrievalEvalCase]:
    """
    从 JSONL 文件加载 Retrieval Eval Cases。

    每行格式：

    {
        "case_id": "...",
        "query": "...",
        "expected_event_ids": ["..."]
    }
    """

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"eval dataset not found: {path}")

    cases: list[RetrievalEvalCase] = []

    seen_case_ids: set[str] = set()

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line_number, raw_line in enumerate(
            file,
            start=1,
        ):
            line = raw_line.strip()

            if not line:
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RetrievalEvalDatasetError(
                    "invalid JSON at " f"line {line_number}"
                ) from exc

            case_id = str(
                payload.get(
                    "case_id",
                    "",
                )
            ).strip()

            query = str(
                payload.get(
                    "query",
                    "",
                )
            ).strip()

            expected_event_ids = payload.get("expected_event_ids", [])

            if not case_id:
                raise RetrievalEvalDatasetError(
                    "case_id is required at " f"line {line_number}"
                )

            if case_id in seen_case_ids:
                raise RetrievalEvalDatasetError("duplicate case_id: " f"{case_id}")

            if not query:
                raise RetrievalEvalDatasetError(
                    "query is required at " f"line {line_number}"
                )

            if (
                not isinstance(
                    expected_event_ids,
                    list,
                )
                or not expected_event_ids
            ):
                raise RetrievalEvalDatasetError(
                    "expected_event_ids must "
                    "be a non-empty list at "
                    f"line {line_number}"
                )

            normalized_event_ids = [
                str(event_id).strip()
                for event_id in expected_event_ids
                if str(event_id).strip()
            ]

            if not normalized_event_ids:
                raise RetrievalEvalDatasetError(
                    "expected_event_ids must "
                    "contain at least one "
                    "non-empty ID at "
                    f"line {line_number}"
                )

            cases.append(
                RetrievalEvalCase(
                    case_id=case_id,
                    query=query,
                    expected_event_ids=(normalized_event_ids),
                )
            )

            seen_case_ids.add(case_id)

    if not cases:
        raise RetrievalEvalDatasetError("eval dataset contains no cases")

    return cases
