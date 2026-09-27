import pytest
from pydantic import ValidationError

from app.domain.event import (
    Event,
    make_event_id,
)


def make_valid_event() -> Event:
    highlight_ids = [
        "highlight-1",
        "highlight-2",
    ]

    return Event(
        id=make_event_id(
            stream_id="stream-1",
            part_id="part-1",
            source_highlight_ids=highlight_ids,
        ),
        stream_id="stream-1",
        part_id="part-1",
        start_ms=1000,
        end_ms=5000,
        peak_ms=3000,
        source_highlight_ids=highlight_ids,
        title="观众集中讨论某个话题",
        summary="该时间段内观众弹幕围绕同一话题集中出现。",
        keywords=[
            "话题",
            "讨论",
        ],
        entities=[
            "example",
        ],
        semantic_text=(
            "观众在该时间段集中讨论某个话题。"
        ),
        semanticizer_version="v1",
    )


def test_event_can_be_created():
    event = make_valid_event()

    assert event.stream_id == "stream-1"
    assert event.part_id == "part-1"
    assert event.start_ms == 1000
    assert event.end_ms == 5000
    assert event.peak_ms == 3000
    assert event.source_highlight_ids == [
        "highlight-1",
        "highlight-2",
    ]


def test_event_id_is_stable_for_same_highlight_set():
    first = make_event_id(
        stream_id="stream-1",
        part_id="part-1",
        source_highlight_ids=[
            "highlight-1",
            "highlight-2",
        ],
    )

    second = make_event_id(
        stream_id="stream-1",
        part_id="part-1",
        source_highlight_ids=[
            "highlight-2",
            "highlight-1",
        ],
    )

    assert first == second


def test_event_id_requires_source_highlights():
    with pytest.raises(
        ValueError,
        match="source_highlight_ids must not be empty",
    ):
        make_event_id(
            stream_id="stream-1",
            part_id="part-1",
            source_highlight_ids=[],
        )


def test_event_rejects_invalid_time_range():
    with pytest.raises(ValidationError):
        Event(
            id="event-1",
            stream_id="stream-1",
            part_id="part-1",
            start_ms=5000,
            end_ms=1000,
            peak_ms=3000,
            source_highlight_ids=[
                "highlight-1",
            ],
            title="title",
            summary="summary",
            semantic_text="semantic text",
            semanticizer_version="v1",
        )


def test_event_rejects_duplicate_source_highlights():
    with pytest.raises(
        ValidationError,
        match="source_highlight_ids must be unique",
    ):
        Event(
            id="event-1",
            stream_id="stream-1",
            part_id="part-1",
            start_ms=1000,
            end_ms=5000,
            peak_ms=3000,
            source_highlight_ids=[
                "highlight-1",
                "highlight-1",
            ],
            title="title",
            summary="summary",
            semantic_text="semantic text",
            semanticizer_version="v1",
        )