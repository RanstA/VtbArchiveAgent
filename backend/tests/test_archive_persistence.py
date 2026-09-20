import sqlite3
from datetime import datetime

import pytest

import app.ingestion.persist as persist_module
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
from app.ingestion.persist import (
    persist_archive_bundle,
)
from app.ingestion.source import (
    ArchiveBundle,
)
from app.repository.database import (
    init_db,
)
from app.repository.danmaku_repo import (
    list_danmaku_by_stream_part,
)
from app.repository.highlight_repo import (
    list_highlights_by_stream,
    replace_highlights_for_stream,
)
from app.repository.stream_part_repo import (
    list_stream_parts,
)
from app.repository.stream_repo import (
    list_streams,
)
from app.repository.vtuber_repo import (
    get_vtuber,
    list_vtuber_sources,
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


def make_bundle(
    *,
    vtuber_name: str = "测试主播",
    status: str = "local",
    danmaku_path: str = "archive.ass",
    danmaku_texts: tuple[
        str,
        ...
    ] = (
        "第一条",
        "第二条",
    ),
    include_parts: bool = True,
) -> ArchiveBundle:
    vtuber = Vtuber(
        id="vtuber-test",
        display_name=vtuber_name,
    )

    live_time = datetime(
        2026,
        9,
        20,
        12,
        0,
    )

    title = "测试直播"

    stream = Stream(
        id=make_stream_id(
            vtuber_id=vtuber.id,
            live_time=live_time,
            title=title,
        ),
        vtuber_id=vtuber.id,
        month="2026-09",
        live_time=live_time,
        publish_times=[],
        bv_ids=[
            "BV1TEST"
        ],
        title=title,
        video_url="",
        status=status,
    )

    vtuber_source = (
        VtuberSource(
            vtuber_id=vtuber.id,
            source="local",
            external_id=None,
            display_name=(
                vtuber_name
            ),
        )
    )

    if not include_parts:
        return ArchiveBundle(
            source="local",
            vtuber=vtuber,
            vtuber_sources=[
                vtuber_source
            ],
            stream=stream,
            parts=[],
            danmaku=[],
            source_metadata={
                "layout": (
                    "metadata_only"
                ),
            },
        )

    part = StreamPart(
        stream_id=stream.id,
        part_id="p0",
        video_path=None,
        danmaku_path=(
            danmaku_path
        ),
        xml_path="archive.xml",
    )

    danmaku = [
        Danmaku(
            stream_id=stream.id,
            part_id="p0",
            timestamp_ms=(
                (index + 1)
                * 1000
            ),
            raw_text=text,
            text=text,
        )
        for index, text
        in enumerate(
            danmaku_texts
        )
    ]

    return ArchiveBundle(
        source="local",
        vtuber=vtuber,
        vtuber_sources=[
            vtuber_source
        ],
        stream=stream,
        parts=[
            part
        ],
        danmaku=danmaku,
        source_metadata={
            "layout": "flat",
        },
    )


def make_highlight(
    stream_id: str,
) -> Highlight:
    return Highlight(
        id=make_highlight_id(
            stream_id=stream_id,
            part_id="p0",
            start_ms=1000,
            end_ms=31_000,
        ),
        stream_id=stream_id,
        part_id="p0",
        start_ms=1000,
        end_ms=31_000,
        peak_ms=10_000,
        score=0.9,
        density_score=0.9,
        repetition_score=0.8,
        reaction_score=0.85,
        danmaku_count=20,
        unique_text_count=10,
        repetition_ratio=0.5,
        reaction_ratio=0.6,
        laugh_count=5,
        question_count=3,
        exclamation_count=2,
        detector_version="v0.1",
    )


def count_rows(
    connection: sqlite3.Connection,
    table_name: str,
) -> int:
    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM {table_name}
        """
    ).fetchone()

    assert row is not None

    return int(
        row[0]
    )


def test_persist_archive_bundle_writes_complete_graph():
    connection = make_connection()

    try:
        bundle = make_bundle()

        persist_archive_bundle(
            connection=connection,
            bundle=bundle,
        )

        stored_vtuber = (
            get_vtuber(
                connection=connection,
                vtuber_id=(
                    bundle.vtuber.id
                ),
            )
        )

        assert (
            stored_vtuber
            == bundle.vtuber
        )

        sources = (
            list_vtuber_sources(
                connection=connection,
                vtuber_id=(
                    bundle.vtuber.id
                ),
            )
        )

        assert (
            sources
            == bundle.vtuber_sources
        )

        streams = list_streams(
            connection=connection,
        )

        assert len(
            streams
        ) == 1

        assert (
            streams[0][
                "vtuber_id"
            ]
            == bundle.vtuber.id
        )

        parts = list_stream_parts(
            connection=connection,
            stream_id=(
                bundle.stream.id
            ),
        )

        assert len(
            parts
        ) == 1

        assert (
            parts[0]["part_id"]
            == "p0"
        )

        danmaku = (
            list_danmaku_by_stream_part(
                connection=connection,
                stream_part_id=(
                    parts[0]["id"]
                ),
                stream_id=(
                    bundle.stream.id
                ),
                part_id="p0",
            )
        )

        assert [
            item.text
            for item
            in danmaku
        ] == [
            "第一条",
            "第二条",
        ]

    finally:
        connection.close()


def test_persist_same_bundle_is_idempotent():
    connection = make_connection()

    try:
        bundle = make_bundle()

        persist_archive_bundle(
            connection=connection,
            bundle=bundle,
        )

        persist_archive_bundle(
            connection=connection,
            bundle=bundle,
        )

        assert (
            count_rows(
                connection,
                "vtubers",
            )
            == 1
        )

        assert (
            count_rows(
                connection,
                "vtuber_sources",
            )
            == 1
        )

        assert (
            count_rows(
                connection,
                "streams",
            )
            == 1
        )

        assert (
            count_rows(
                connection,
                "stream_bv_ids",
            )
            == 1
        )

        assert (
            count_rows(
                connection,
                "stream_parts",
            )
            == 1
        )

        assert (
            count_rows(
                connection,
                "danmaku",
            )
            == 2
        )

    finally:
        connection.close()


def test_metadata_only_bundle_keeps_existing_payload():
    connection = make_connection()

    try:
        complete = make_bundle()

        persist_archive_bundle(
            connection=connection,
            bundle=complete,
        )

        metadata_only = make_bundle(
            status="metadata_only",
            include_parts=False,
        )

        persist_archive_bundle(
            connection=connection,
            bundle=metadata_only,
        )

        parts = list_stream_parts(
            connection=connection,
            stream_id=(
                complete.stream.id
            ),
        )

        assert len(
            parts
        ) == 1

        danmaku = (
            list_danmaku_by_stream_part(
                connection=connection,
                stream_part_id=(
                    parts[0]["id"]
                ),
                stream_id=(
                    complete.stream.id
                ),
                part_id="p0",
            )
        )

        assert len(
            danmaku
        ) == 2

        streams = list_streams(
            connection=connection,
        )

        assert (
            streams[0]["status"]
            == "metadata_only"
        )

    finally:
        connection.close()


def test_successful_reimport_replaces_payload_and_invalidates_highlights():
    connection = make_connection()

    try:
        original = make_bundle(
            danmaku_path="old.ass",
            danmaku_texts=(
                "旧弹幕一",
                "旧弹幕二",
            ),
        )

        persist_archive_bundle(
            connection=connection,
            bundle=original,
        )

        highlight = make_highlight(
            original.stream.id
        )

        replace_highlights_for_stream(
            connection=connection,
            stream_id=(
                original.stream.id
            ),
            highlights=[
                highlight
            ],
        )

        replacement = make_bundle(
            status="updated",
            danmaku_path="new.ass",
            danmaku_texts=(
                "新弹幕",
            ),
        )

        persist_archive_bundle(
            connection=connection,
            bundle=replacement,
        )

        parts = list_stream_parts(
            connection=connection,
            stream_id=(
                original.stream.id
            ),
        )

        assert len(
            parts
        ) == 1

        assert (
            parts[0][
                "danmaku_path"
            ]
            == "new.ass"
        )

        danmaku = (
            list_danmaku_by_stream_part(
                connection=connection,
                stream_part_id=(
                    parts[0]["id"]
                ),
                stream_id=(
                    original.stream.id
                ),
                part_id="p0",
            )
        )

        assert [
            item.text
            for item
            in danmaku
        ] == [
            "新弹幕"
        ]

        highlights = (
            list_highlights_by_stream(
                connection=connection,
                stream_id=(
                    original.stream.id
                ),
            )
        )

        assert (
            highlights
            == []
        )

    finally:
        connection.close()


def test_failed_reimport_rolls_back_entire_bundle(
    monkeypatch,
):
    connection = make_connection()

    try:
        original = make_bundle(
            vtuber_name="旧名字",
            status="old",
            danmaku_path="old.ass",
            danmaku_texts=(
                "旧弹幕一",
                "旧弹幕二",
            ),
        )

        persist_archive_bundle(
            connection=connection,
            bundle=original,
        )

        highlight = make_highlight(
            original.stream.id
        )

        replace_highlights_for_stream(
            connection=connection,
            stream_id=(
                original.stream.id
            ),
            highlights=[
                highlight
            ],
        )

        replacement = make_bundle(
            vtuber_name="新名字",
            status="new",
            danmaku_path="new.ass",
            danmaku_texts=(
                "新弹幕",
            ),
        )

        def fail_insert_danmaku(
            connection,
            stream_part_id,
            danmaku,
        ):
            raise RuntimeError(
                "simulated danmaku failure"
            )

        monkeypatch.setattr(
            persist_module,
            "insert_danmaku_batch",
            fail_insert_danmaku,
        )

        with pytest.raises(
            RuntimeError,
            match=(
                "simulated danmaku failure"
            ),
        ):
            persist_archive_bundle(
                connection=connection,
                bundle=replacement,
            )

        stored_vtuber = (
            get_vtuber(
                connection=connection,
                vtuber_id="vtuber-test",
            )
        )

        assert (
            stored_vtuber
            is not None
        )

        assert (
            stored_vtuber
            .display_name
            == "旧名字"
        )

        sources = (
            list_vtuber_sources(
                connection=connection,
                vtuber_id="vtuber-test",
            )
        )

        assert (
            sources[0]
            .display_name
            == "旧名字"
        )

        streams = list_streams(
            connection=connection,
        )

        assert (
            streams[0]["status"]
            == "old"
        )

        parts = list_stream_parts(
            connection=connection,
            stream_id=(
                original.stream.id
            ),
        )

        assert len(
            parts
        ) == 1

        assert (
            parts[0][
                "danmaku_path"
            ]
            == "old.ass"
        )

        danmaku = (
            list_danmaku_by_stream_part(
                connection=connection,
                stream_part_id=(
                    parts[0]["id"]
                ),
                stream_id=(
                    original.stream.id
                ),
                part_id="p0",
            )
        )

        assert [
            item.text
            for item
            in danmaku
        ] == [
            "旧弹幕一",
            "旧弹幕二",
        ]

        highlights = (
            list_highlights_by_stream(
                connection=connection,
                stream_id=(
                    original.stream.id
                ),
            )
        )

        assert len(
            highlights
        ) == 1

        assert (
            highlights[0].id
            == highlight.id
        )

    finally:
        connection.close()