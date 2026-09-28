import pytest
from pydantic import ValidationError

from app.domain.event import (
    Event,
    make_event_id,
)


def make_valid_event() -> Event:
    return Event(
        id=make_event_id(
            stream_id="stream-1",
            start_ms=3_120_000,
            end_ms=3_260_000,
        ),
        stream_id="stream-1",
        source_part_ids=[
            "p0",
            "p1",
        ],
        start_ms=3_120_000,
        end_ms=3_260_000,
        anchor_ms=3_180_000,
        source_highlight_ids=[
            "highlight-1",
            "highlight-2",
        ],
        title="观众集中讨论某个话题",
        summary=("该时间段内观众弹幕" "围绕同一话题集中出现。"),
        keywords=[
            "话题",
            "讨论",
        ],
        entities=[
            "example",
        ],
        semantic_text=("观众在该时间段" "集中讨论某个话题。"),
        salience_score=0.8,
        segmenter_version=("topic-segmenter-v1"),
        semanticizer_version="v1",
    )


def test_event_can_cross_parts():
    event = make_valid_event()

    assert event.stream_id == "stream-1"

    assert event.source_part_ids == [
        "p0",
        "p1",
    ]

    assert event.start_ms == 3_120_000
    assert event.end_ms == 3_260_000
    assert event.anchor_ms == 3_180_000

    assert event.salience_score == 0.8


def test_event_can_exist_without_highlights():
    event = make_valid_event().model_copy(
        update={
            "source_highlight_ids": [],
            "salience_score": 0.0,
        }
    )

    assert event.source_highlight_ids == []

    assert event.salience_score == 0.0


def test_event_id_is_stable_for_same_boundary():
    first = make_event_id(
        stream_id="stream-1",
        start_ms=1000,
        end_ms=5000,
    )

    second = make_event_id(
        stream_id="stream-1",
        start_ms=1000,
        end_ms=5000,
    )

    assert first == second


def test_event_id_changes_when_boundary_changes():
    first = make_event_id(
        stream_id="stream-1",
        start_ms=1000,
        end_ms=5000,
    )

    second = make_event_id(
        stream_id="stream-1",
        start_ms=1000,
        end_ms=6000,
    )

    assert first != second


def test_event_id_rejects_invalid_time_range():
    with pytest.raises(
        ValueError,
        match=("end_ms must be greater " "than start_ms"),
    ):
        make_event_id(
            stream_id="stream-1",
            start_ms=5000,
            end_ms=1000,
        )


def test_event_requires_source_parts():
    data = make_valid_event().model_dump()

    data["source_part_ids"] = []

    with pytest.raises(
        ValidationError,
    ):
        Event(**data)


def test_event_rejects_duplicate_source_parts():
    data = make_valid_event().model_dump()

    data["source_part_ids"] = [
        "p0",
        "p0",
    ]

    with pytest.raises(
        ValidationError,
        match=("source_part_ids " "must be unique"),
    ):
        Event(**data)


def test_event_rejects_anchor_outside_range():
    data = make_valid_event().model_dump()

    data["anchor_ms"] = data["end_ms"]

    with pytest.raises(
        ValidationError,
        match=("anchor_ms must be inside"),
    ):
        Event(**data)


def test_event_rejects_duplicate_source_highlights():
    data = make_valid_event().model_dump()

    data["source_highlight_ids"] = [
        "highlight-1",
        "highlight-1",
    ]

    with pytest.raises(
        ValidationError,
        match=("source_highlight_ids " "must be unique"),
    ):
        Event(**data)


@pytest.mark.parametrize(
    "salience_score",
    [
        -0.1,
        1.1,
    ],
)
def test_event_rejects_invalid_salience_score(
    salience_score: float,
):
    data = make_valid_event().model_dump()

    data["salience_score"] = salience_score

    with pytest.raises(
        ValidationError,
    ):
        Event(**data)
