import json
from pathlib import Path

import pytest

from evals.retrieval.dataset import (
    RetrievalEvalDatasetError,
    load_retrieval_eval_cases,
)


def test_load_retrieval_eval_cases(
    tmp_path: Path,
):
    path = tmp_path / "retrieval.jsonl"

    rows = [
        {
            "case_id": "cat",
            "query": "他以前聊过猫吗？",
            "expected_event_ids": [
                "event-cat",
            ],
        },
        {
            "case_id": "game",
            "query": "哪次聊过游戏失败？",
            "expected_event_ids": [
                "event-game-1",
                "event-game-2",
            ],
        },
    ]

    path.write_text(
        "\n".join(
            json.dumps(
                row,
                ensure_ascii=False,
            )
            for row in rows
        ),
        encoding="utf-8",
    )

    cases = load_retrieval_eval_cases(path)

    assert len(cases) == 2

    assert cases[0].case_id == "cat"

    assert cases[0].query == "他以前聊过猫吗？"

    assert cases[0].expected_event_ids == ["event-cat"]

    assert cases[1].expected_event_ids == [
        "event-game-1",
        "event-game-2",
    ]


def test_rejects_duplicate_case_id(
    tmp_path: Path,
):
    path = tmp_path / "retrieval.jsonl"

    rows = [
        {
            "case_id": "same",
            "query": "query-1",
            "expected_event_ids": [
                "event-1",
            ],
        },
        {
            "case_id": "same",
            "query": "query-2",
            "expected_event_ids": [
                "event-2",
            ],
        },
    ]

    path.write_text(
        "\n".join(json.dumps(row) for row in rows),
        encoding="utf-8",
    )

    with pytest.raises(
        RetrievalEvalDatasetError,
        match="duplicate case_id",
    ):
        load_retrieval_eval_cases(path)


def test_rejects_empty_expected_events(
    tmp_path: Path,
):
    path = tmp_path / "retrieval.jsonl"

    path.write_text(
        json.dumps(
            {
                "case_id": "cat",
                "query": "聊过猫吗",
                "expected_event_ids": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        RetrievalEvalDatasetError,
        match=("expected_event_ids must " "be a non-empty list"),
    ):
        load_retrieval_eval_cases(path)


def test_rejects_invalid_json(
    tmp_path: Path,
):
    path = tmp_path / "retrieval.jsonl"

    path.write_text(
        "{not-json}",
        encoding="utf-8",
    )

    with pytest.raises(
        RetrievalEvalDatasetError,
        match="invalid JSON",
    ):
        load_retrieval_eval_cases(path)
