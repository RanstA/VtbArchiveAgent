from datetime import (
    datetime,
)
from pathlib import Path

from fastapi.testclient import (
    TestClient,
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
