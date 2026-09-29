import sqlite3
from datetime import datetime

from app.catchup.builder import (
    build_stream_descriptor,
)
from app.event_pipeline.timeline import (
    StreamTimeline,
    TimelineItem,
)


def test_build_stream_descriptor_uses_timeline(
    monkeypatch,
):
    connection = sqlite3.connect(":memory:")

    stream = {
        "id": "stream-1",
        "title": "测试直播",
        "live_time": ("2026-09-29T20:00:00"),
        "bv_ids": ["BVTEST"],
    }

    timeline = StreamTimeline(
        stream_id="stream-1",
        duration_ms=220_000,
        merge_gap_ms=20_000,
        items=[
            TimelineItem(
                id="item-1",
                stream_id="stream-1",
                source_part_ids=["p0"],
                start_ms=20_000,
                end_ms=50_000,
                anchor_ms=35_000,
                local_anchor_ms=35_000,
                salience_score=0.96,
                source_highlight_ids=["h1"],
            ),
            TimelineItem(
                id="item-2",
                stream_id="stream-1",
                source_part_ids=["p1"],
                start_ms=110_000,
                end_ms=140_000,
                anchor_ms=120_000,
                local_anchor_ms=20_000,
                salience_score=0.91,
                source_highlight_ids=["h2"],
            ),
            TimelineItem(
                id="item-3",
                stream_id="stream-1",
                source_part_ids=["p1"],
                start_ms=150_000,
                end_ms=180_000,
                anchor_ms=160_000,
                local_anchor_ms=60_000,
                salience_score=0.97,
                title="神秘园环节",
                summary="主播进入神秘园相关话题。",
                keywords=["神秘园"],
                entities=["神秘园"],
                evidence_refs=["danmaku:h3", "asr:test-1"],
                source_highlight_ids=["h3"],
            ),
        ],
    )

    monkeypatch.setattr(
        "app.catchup.builder.get_stream_by_id",
        lambda **_: stream,
    )

    monkeypatch.setattr(
        "app.catchup.builder.build_stream_timeline",
        lambda **_: timeline,
    )

    try:
        descriptor = build_stream_descriptor(
            connection=connection,
            stream_id="stream-1",
        )
    finally:
        connection.close()

    assert descriptor is not None

    assert descriptor.title == "测试直播"

    assert descriptor.live_time == datetime(
        2026,
        9,
        29,
        20,
        0,
    )

    assert descriptor.duration_ms == 220_000

    assert descriptor.bv_ids == ["BVTEST"]

    assert len(descriptor.important_moments) == 2

    assert [item.anchor_ms for item in descriptor.important_moments] == [
        35_000,
        160_000,
    ]

    assert descriptor.important_moments[1].local_anchor_ms == 60_000
    
    assert len(
        descriptor.events
    ) == 1

    event = descriptor.events[0]

    assert event.anchor_ms == 160_000

    assert event.local_anchor_ms == 60_000

    assert event.title == "神秘园环节"

    assert (
        event.summary
        == "主播进入神秘园相关话题。"
    )

    assert event.keywords == [
        "神秘园",
    ]

    assert event.entities == [
        "神秘园",
    ]

    assert event.evidence_refs == [
        "danmaku:h3",
        "asr:test-1",
    ]


def test_build_stream_descriptor_returns_none_for_missing_stream(
    monkeypatch,
):
    connection = sqlite3.connect(":memory:")

    monkeypatch.setattr(
        "app.catchup.builder.get_stream_by_id",
        lambda **_: None,
    )

    try:
        descriptor = build_stream_descriptor(
            connection=connection,
            stream_id="missing",
        )
    finally:
        connection.close()

    assert descriptor is None


def test_build_stream_descriptor_returns_none_when_timeline_is_missing(
    monkeypatch,
):
    connection = sqlite3.connect(":memory:")

    stream = {
        "id": "stream-1",
        "title": "测试直播",
        "live_time": ("2026-09-29T20:00:00"),
        "bv_ids": ["BVTEST"],
    }

    monkeypatch.setattr(
        "app.catchup.builder.get_stream_by_id",
        lambda **_: stream,
    )

    monkeypatch.setattr(
        "app.catchup.builder.build_stream_timeline",
        lambda **_: None,
    )

    try:
        descriptor = build_stream_descriptor(
            connection=connection,
            stream_id="stream-1",
        )
    finally:
        connection.close()

    assert descriptor is None
