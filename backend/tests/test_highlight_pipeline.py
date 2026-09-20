import sqlite3
from datetime import datetime

from app.domain.danmaku import (
    Danmaku,
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
    VtuberSource,
)
from app.event_pipeline.highlights import (
    generate_highlights_for_stream,
)
from app.ingestion.persist import (
    persist_archive_bundle,
)
from app.ingestion.source import (
    ArchiveBundle,
)
from app.repository.database import (
    init_db,
)
from app.repository.highlight_repo import (
    list_highlights_by_stream,
    replace_highlights_for_stream,
)


def make_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(
        ":memory:"
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    init_db(
        connection
    )

    return connection


def make_stream() -> Stream:
    live_time = datetime(
        2026,
        9,
        20,
        12,
        0,
    )

    title = "测试直播"

    return Stream(
        id=make_stream_id(
            vtuber_id="vtuber-test",
            live_time=live_time,
            title=title,
        ),
        vtuber_id="vtuber-test",
        month="2026-09",
        live_time=live_time,
        publish_times=[],
        bv_ids=[],
        title=title,
        video_url="",
        status="local",
    )


def make_burst_danmaku(
    stream_id: str,
) -> list[Danmaku]:
    """
    构造一个明显的局部高光：

        35s: 少量普通弹幕
        45s: 大量强反应
        65s: 大量强反应
        75s: 少量普通弹幕

    因此 40s ~ 70s 窗口会同时获得：

        更高 density
        更高 repetition
        更高 reaction

    成为明显局部峰。
    """

    result: list[
        Danmaku
    ] = []

    for index in range(5):
        text = (
            f"普通弹幕-left-{index}"
        )

        result.append(
            Danmaku(
                stream_id=stream_id,
                part_id="p0",
                timestamp_ms=(
                    35_000
                    + index
                ),
                raw_text=text,
                text=text,
            )
        )

    for index in range(30):
        result.append(
            Danmaku(
                stream_id=stream_id,
                part_id="p0",
                timestamp_ms=(
                    45_000
                    + index
                ),
                raw_text="？？？",
                text="？？？",
            )
        )

    for index in range(30):
        result.append(
            Danmaku(
                stream_id=stream_id,
                part_id="p0",
                timestamp_ms=(
                    65_000
                    + index
                ),
                raw_text="？？？",
                text="？？？",
            )
        )

    for index in range(5):
        text = (
            f"普通弹幕-right-{index}"
        )

        result.append(
            Danmaku(
                stream_id=stream_id,
                part_id="p0",
                timestamp_ms=(
                    75_000
                    + index
                ),
                raw_text=text,
                text=text,
            )
        )

    return result


def make_bundle(
    *,
    with_danmaku: bool = True,
) -> ArchiveBundle:
    vtuber = Vtuber(
        id="vtuber-test",
        display_name="测试主播",
    )

    stream = make_stream()

    part = StreamPart(
        stream_id=stream.id,
        part_id="p0",
    )

    danmaku = (
        make_burst_danmaku(
            stream.id
        )
        if with_danmaku
        else []
    )

    return ArchiveBundle(
        source="local",
        vtuber=vtuber,
        vtuber_sources=[
            VtuberSource(
                vtuber_id=vtuber.id,
                source="local",
                external_id=None,
                display_name=(
                    vtuber.display_name
                ),
            )
        ],
        stream=stream,
        parts=[
            part
        ],
        danmaku=danmaku,
    )


def test_generate_highlights_for_stream():
    connection = make_connection()

    try:
        bundle = make_bundle()

        persist_archive_bundle(
            connection=connection,
            bundle=bundle,
        )

        highlights = (
            generate_highlights_for_stream(
                connection=connection,
                stream_id=(
                    bundle.stream.id
                ),
            )
        )

        assert (
            len(highlights)
            >= 1
        )

        top = highlights[0]

        assert (
            top.stream_id
            == bundle.stream.id
        )

        assert (
            top.part_id
            == "p0"
        )

        assert (
            top.detector_version
            == "v0.1"
        )

        assert (
            top.score
            >= 0.85
        )

        assert (
            top.start_ms
            == 40_000
        )

        assert (
            top.end_ms
            == 70_000
        )

        # 40~50 与 60~70
        # 都有同样数量的强反应。
        #
        # find_peak_ms 在完全相同时
        # 保留较早的 10 秒窗口，
        # 因而锚点为 45 秒。
        assert (
            top.peak_ms
            == 45_000
        )

        assert (
            top.id
            == make_highlight_id(
                stream_id=(
                    bundle.stream.id
                ),
                part_id="p0",
                start_ms=40_000,
                end_ms=70_000,
            )
        )

        stored = (
            list_highlights_by_stream(
                connection=connection,
                stream_id=(
                    bundle.stream.id
                ),
            )
        )

        assert (
            len(stored)
            == len(highlights)
        )

        assert {
            item.id
            for item in stored
        } == {
            item.id
            for item in highlights
        }

    finally:
        connection.close()


def test_regenerating_highlights_does_not_duplicate_rows():
    connection = make_connection()

    try:
        bundle = make_bundle()

        persist_archive_bundle(
            connection=connection,
            bundle=bundle,
        )

        first = (
            generate_highlights_for_stream(
                connection=connection,
                stream_id=(
                    bundle.stream.id
                ),
            )
        )

        second = (
            generate_highlights_for_stream(
                connection=connection,
                stream_id=(
                    bundle.stream.id
                ),
            )
        )

        assert [
            item.id
            for item in first
        ] == [
            item.id
            for item in second
        ]

        stored = (
            list_highlights_by_stream(
                connection=connection,
                stream_id=(
                    bundle.stream.id
                ),
            )
        )

        assert (
            len(stored)
            == len(first)
        )

    finally:
        connection.close()


def test_generation_with_no_danmaku_clears_stale_highlights():
    connection = make_connection()

    try:
        bundle = make_bundle(
            with_danmaku=False,
        )

        persist_archive_bundle(
            connection=connection,
            bundle=bundle,
        )

        stale = Highlight(
            id=make_highlight_id(
                stream_id=(
                    bundle.stream.id
                ),
                part_id="p0",
                start_ms=0,
                end_ms=30_000,
            ),
            stream_id=(
                bundle.stream.id
            ),
            part_id="p0",
            start_ms=0,
            end_ms=30_000,
            peak_ms=15_000,
            score=0.9,
            density_score=0.9,
            repetition_score=0.9,
            reaction_score=0.9,
            danmaku_count=100,
            unique_text_count=10,
            repetition_ratio=0.9,
            reaction_ratio=0.9,
            laugh_count=20,
            question_count=20,
            exclamation_count=20,
            detector_version="old",
        )

        replace_highlights_for_stream(
            connection=connection,
            stream_id=(
                bundle.stream.id
            ),
            highlights=[
                stale
            ],
        )

        assert len(
            list_highlights_by_stream(
                connection=connection,
                stream_id=(
                    bundle.stream.id
                ),
            )
        ) == 1

        generated = (
            generate_highlights_for_stream(
                connection=connection,
                stream_id=(
                    bundle.stream.id
                ),
            )
        )

        assert (
            generated
            == []
        )

        assert (
            list_highlights_by_stream(
                connection=connection,
                stream_id=(
                    bundle.stream.id
                ),
            )
            == []
        )

    finally:
        connection.close()