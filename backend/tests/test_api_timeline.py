from datetime import (
    datetime,
)
from pathlib import Path

from fastapi.testclient import (
    TestClient,
)
from app.domain.event import (
    Event,
    make_event_id,
)
from app.event_pipeline.timeline import (
    build_stream_timeline,
)
from app.repository.event_repo import (
    upsert_event,
)
from app.config.settings import (
    settings,
)
from app.domain.highlight import (
    Highlight,
    make_highlight_id,
)
from app.domain.stream import (
    Stream,
    make_stream_id,
)
from app.domain.stream_part import (
    StreamPart,
)
from app.domain.vtuber import (
    Vtuber,
)
from app.main import app
from app.repository.database import (
    connect_db,
    init_db,
)
from app.repository.highlight_repo import (
    replace_highlights_for_stream,
)
from app.repository.stream_part_repo import (
    insert_stream_part,
)
from app.repository.stream_repo import (
    insert_stream,
)
from app.repository.vtuber_repo import (
    insert_vtuber,
)

client = TestClient(app)


def make_highlight(
    *,
    stream_id: str,
    part_id: str,
    start_ms: int,
    end_ms: int,
    peak_ms: int,
    score: float,
) -> Highlight:
    return Highlight(
        id=make_highlight_id(
            stream_id=stream_id,
            part_id=part_id,
            start_ms=start_ms,
            end_ms=end_ms,
        ),
        stream_id=stream_id,
        part_id=part_id,
        start_ms=start_ms,
        end_ms=end_ms,
        peak_ms=peak_ms,
        score=score,
        density_score=score,
        repetition_score=score,
        reaction_score=score,
        danmaku_count=100,
        unique_text_count=40,
        repetition_ratio=0.5,
        reaction_ratio=0.6,
        laugh_count=10,
        question_count=5,
        exclamation_count=8,
        detector_version="v0.1",
    )


def prepare_database(
    db_path: Path,
) -> tuple[
    str,
    Highlight,
    Highlight,
    Highlight,
]:
    connection = connect_db(db_path)

    try:
        init_db(connection)

        vtuber = Vtuber(
            id="aza",
            display_name="阿萨Aza",
        )

        insert_vtuber(
            connection=connection,
            vtuber=vtuber,
        )

        live_time = datetime(
            2026,
            9,
            20,
            19,
            0,
        )

        stream_id = make_stream_id(
            vtuber_id="aza",
            live_time=live_time,
            title="Timeline 测试直播",
        )

        stream = Stream(
            id=stream_id,
            vtuber_id="aza",
            month="2026-09",
            live_time=live_time,
            publish_times=[],
            bv_ids=["BVTEST"],
            title="Timeline 测试直播",
            video_url="",
            status="online",
        )

        insert_stream(
            connection=connection,
            stream=stream,
        )

        insert_stream_part(
            connection=connection,
            part=StreamPart(
                stream_id=stream_id,
                part_id="p0",
                start_offset_ms=0,
                duration_ms=100_000,
            ),
        )

        insert_stream_part(
            connection=connection,
            part=StreamPart(
                stream_id=stream_id,
                part_id="p1",
                start_offset_ms=100_000,
                duration_ms=120_000,
            ),
        )

        p0 = make_highlight(
            stream_id=stream_id,
            part_id="p0",
            start_ms=20_000,
            end_ms=50_000,
            peak_ms=35_000,
            score=0.96,
        )

        p1_first = make_highlight(
            stream_id=stream_id,
            part_id="p1",
            start_ms=10_000,
            end_ms=40_000,
            peak_ms=20_000,
            score=0.91,
        )

        p1_second = make_highlight(
            stream_id=stream_id,
            part_id="p1",
            start_ms=50_000,
            end_ms=80_000,
            peak_ms=60_000,
            score=0.97,
        )

        replace_highlights_for_stream(
            connection=connection,
            stream_id=stream_id,
            highlights=[
                p0,
                p1_first,
                p1_second,
            ],
        )

        return (
            stream_id,
            p0,
            p1_first,
            p1_second,
        )

    finally:
        connection.close()


def test_timeline_converts_to_stream_global_time(
    tmp_path: Path,
    monkeypatch,
):
    db_path = tmp_path / "timeline.db"

    (
        stream_id,
        p0,
        p1_first,
        p1_second,
    ) = prepare_database(db_path)

    monkeypatch.setattr(
        settings,
        "database_path",
        db_path,
    )

    response = client.get(f"/streams/{stream_id}/timeline")

    assert response.status_code == 200

    payload = response.json()

    assert payload["streamId"] == stream_id

    assert payload["durationMs"] == 220_000

    assert payload["mergeGapMs"] == 20_000

    items = payload["items"]

    assert len(items) == 2

    first = items[0]

    assert first["sourcePartIds"] == ["p0"]

    assert first["startMs"] == 20_000

    assert first["endMs"] == 50_000

    assert first["anchorMs"] == 35_000

    assert first["localAnchorMs"] == 35_000

    assert first["salienceScore"] == 0.96

    assert first["sourceHighlightIds"] == [
        p0.id,
    ]

    second = items[1]

    assert second["sourcePartIds"] == ["p1"]

    # p1 的 Stream-global offset
    # 是 100 秒。
    assert second["startMs"] == 110_000

    assert second["endMs"] == 180_000

    # 两个 Highlight 被 20s merge。
    # score 更高的第二个 Highlight
    # 提供 anchor。
    assert second["anchorMs"] == 160_000

    assert second["localAnchorMs"] == 60_000

    assert second["salienceScore"] == 0.97

    assert second["sourceHighlightIds"] == [
        p1_first.id,
        p1_second.id,
    ]


def test_unknown_stream_timeline_returns_404(
    tmp_path: Path,
    monkeypatch,
):
    db_path = tmp_path / "timeline.db"

    prepare_database(db_path)

    monkeypatch.setattr(
        settings,
        "database_path",
        db_path,
    )

    response = client.get("/streams/missing/timeline")

    assert response.status_code == 404


def test_timeline_prefers_persisted_events(
    tmp_path: Path,
):
    db_path = tmp_path / "timeline.db"

    (
        stream_id,
        _,
        _,
        p1_second,
    ) = prepare_database(db_path)

    connection = connect_db(db_path)

    try:
        event = Event(
            id=make_event_id(
                stream_id=stream_id,
                start_ms=120_000,
                end_ms=180_000,
            ),
            stream_id=stream_id,
            source_part_ids=[
                "p1",
            ],
            start_ms=120_000,
            end_ms=180_000,
            anchor_ms=160_000,
            source_highlight_ids=[
                p1_second.id,
            ],
            title="神秘园环节",
            summary=("主播进入神秘园相关话题。"),
            keywords=[
                "神秘园",
            ],
            entities=[
                "神秘园",
            ],
            semantic_text=("神秘园环节\n" "主播进入神秘园相关话题。\n" "神秘园"),
            salience_score=0.97,
            segmenter_version=("highlight-merge-v1"),
            semanticizer_version="v1",
        )

        upsert_event(
            connection=connection,
            event=event,
        )

        timeline = build_stream_timeline(
            connection=connection,
            stream_id=stream_id,
        )

        assert timeline is not None

        # 原始 Highlight fallback
        # 会生成 2 个 TimelineItem。
        #
        # 一旦 persisted Event 存在，
        # Timeline 应优先使用 Event，
        # 所以这里只剩 1 个。
        # persisted Event 只替代它覆盖的 fallback，
        # 其他尚未语义化的 TimelineItem 仍然保留。
        assert len(timeline.items) == 2

        semantic_items = [
            item
            for item in timeline.items
            if item.id == event.id
        ]

        assert len(semantic_items) == 1

        item = semantic_items[0]

        assert item.title == ("神秘园环节")

        assert item.summary == ("主播进入神秘园相关话题。")

        assert item.keywords == [
            "神秘园",
        ]

        assert item.entities == [
            "神秘园",
        ]

        assert item.anchor_ms == 160_000

        # p1 offset = 100_000
        assert item.local_anchor_ms == 60_000

        assert item.evidence_refs == [
            ("highlight:" f"{p1_second.id}"),
        ]

        assert item.source_highlight_ids == [
            p1_second.id,
        ]
        
        fallback_items = [
            item
            for item in timeline.items
            if item.id != event.id
        ]

        assert len(fallback_items) == 1

        fallback = fallback_items[0]

        assert fallback.source_part_ids == [
            "p0",
        ]

        assert fallback.title is None
        assert fallback.summary is None

    finally:
        connection.close()
        
def test_timeline_api_exposes_event_semantics(
    tmp_path: Path,
    monkeypatch,
):
    db_path = tmp_path / "timeline.db"

    (
        stream_id,
        _,
        _,
        p1_second,
    ) = prepare_database(db_path)

    connection = connect_db(db_path)

    try:
        event = Event(
            id=make_event_id(
                stream_id=stream_id,
                start_ms=120_000,
                end_ms=180_000,
            ),
            stream_id=stream_id,
            source_part_ids=["p1"],
            start_ms=120_000,
            end_ms=180_000,
            anchor_ms=160_000,
            source_highlight_ids=[
                p1_second.id,
            ],
            title="神秘园环节",
            summary="主播进入神秘园相关话题。",
            keywords=["神秘园"],
            entities=["神秘园"],
            semantic_text=(
                "神秘园环节\n"
                "主播进入神秘园相关话题。\n"
                "神秘园"
            ),
            salience_score=0.97,
            segmenter_version=(
                "highlight-merge-v1"
            ),
            semanticizer_version="v1",
        )

        upsert_event(
            connection=connection,
            event=event,
        )

    finally:
        connection.close()

    monkeypatch.setattr(
        settings,
        "database_path",
        db_path,
    )

    response = client.get(
        f"/streams/{stream_id}/timeline"
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload["items"]) == 2

    semantic_items = [
        item
        for item in payload["items"]
        if item["title"] == "神秘园环节"
    ]

    assert len(semantic_items) == 1

    item = semantic_items[0]

    assert item["title"] == "神秘园环节"

    assert (
        item["summary"]
        == "主播进入神秘园相关话题。"
    )

    assert item["keywords"] == [
        "神秘园",
    ]

    assert item["entities"] == [
        "神秘园",
    ]

    assert item["evidenceRefs"] == [
        f"highlight:{p1_second.id}",
    ]
