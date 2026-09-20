import sqlite3
from datetime import datetime

from app.domain.highlight import (
    Highlight,
    make_highlight_id,
)
from app.domain.stream import (
    Stream,
    make_stream_id,
)
from app.domain.vtuber import (
    Vtuber,
)
from app.repository.database import (
    init_db,
)
from app.repository.stream_repo import (
    insert_stream,
)
from app.repository.vtuber_repo import (
    insert_vtuber,
)
import scripts.generate_highlights as generate_script


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


def insert_test_stream(
    connection: sqlite3.Connection,
    *,
    vtuber_id: str,
    title: str,
    minute: int,
) -> Stream:
    live_time = datetime(
        2026,
        9,
        20,
        12,
        minute,
    )

    stream = Stream(
        id=make_stream_id(
            vtuber_id=vtuber_id,
            live_time=live_time,
            title=title,
        ),
        vtuber_id=vtuber_id,
        month="2026-09",
        live_time=live_time,
        publish_times=[],
        bv_ids=[],
        title=title,
        video_url="",
        status="local",
    )

    insert_stream(
        connection=connection,
        stream=stream,
    )

    return stream


def test_select_streams_by_vtuber_and_limit():
    connection = make_connection()

    try:
        first_vtuber = Vtuber(
            id="vtuber-a",
            display_name="主播 A",
        )

        second_vtuber = Vtuber(
            id="vtuber-b",
            display_name="主播 B",
        )

        insert_vtuber(
            connection=connection,
            vtuber=first_vtuber,
        )

        insert_vtuber(
            connection=connection,
            vtuber=second_vtuber,
        )

        older = insert_test_stream(
            connection,
            vtuber_id="vtuber-a",
            title="较早直播",
            minute=0,
        )

        newer = insert_test_stream(
            connection,
            vtuber_id="vtuber-a",
            title="较新直播",
            minute=10,
        )

        insert_test_stream(
            connection,
            vtuber_id="vtuber-b",
            title="另一个主播",
            minute=20,
        )

        connection.commit()

        selected = (
            generate_script
            .select_streams(
                connection=connection,
                vtuber_id="vtuber-a",
                limit=1,
            )
        )

        assert len(
            selected
        ) == 1

        assert (
            selected[0]["id"]
            == newer.id
        )

        assert (
            selected[0]["id"]
            != older.id
        )

    finally:
        connection.close()


def test_select_streams_by_exact_stream_id():
    connection = make_connection()

    try:
        vtuber = Vtuber(
            id="vtuber-test",
            display_name="测试主播",
        )

        insert_vtuber(
            connection=connection,
            vtuber=vtuber,
        )

        target = insert_test_stream(
            connection,
            vtuber_id=vtuber.id,
            title="目标直播",
            minute=0,
        )

        insert_test_stream(
            connection,
            vtuber_id=vtuber.id,
            title="其他直播",
            minute=10,
        )

        connection.commit()

        selected = (
            generate_script
            .select_streams(
                connection=connection,
                stream_id=target.id,
            )
        )

        assert len(
            selected
        ) == 1

        assert (
            selected[0]["id"]
            == target.id
        )

    finally:
        connection.close()


def test_generate_for_stream_reports_detector_result(
    monkeypatch,
):
    connection = make_connection()

    try:
        vtuber = Vtuber(
            id="vtuber-test",
            display_name="测试主播",
        )

        insert_vtuber(
            connection=connection,
            vtuber=vtuber,
        )

        stream = insert_test_stream(
            connection,
            vtuber_id=vtuber.id,
            title="测试直播",
            minute=0,
        )

        connection.commit()

        expected = Highlight(
            id=make_highlight_id(
                stream_id=stream.id,
                part_id="p0",
                start_ms=10_000,
                end_ms=40_000,
            ),
            stream_id=stream.id,
            part_id="p0",
            start_ms=10_000,
            end_ms=40_000,
            peak_ms=25_000,
            score=0.91,
            density_score=0.95,
            repetition_score=0.80,
            reaction_score=0.90,
            danmaku_count=100,
            unique_text_count=40,
            repetition_ratio=0.5,
            reaction_ratio=0.6,
            laugh_count=20,
            question_count=10,
            exclamation_count=5,
            detector_version="v0.1",
        )

        def fake_generate(
            connection,
            stream_id,
            *,
            min_score,
        ):
            assert (
                stream_id
                == stream.id
            )

            assert (
                min_score
                == 0.85
            )

            return [
                expected
            ]

        monkeypatch.setattr(
            generate_script,
            "generate_highlights_for_stream",
            fake_generate,
        )

        selected = (
            generate_script
            .select_streams(
                connection=connection,
                stream_id=stream.id,
            )
        )

        (
            result,
            highlights,
        ) = (
            generate_script
            .generate_for_stream(
                connection=connection,
                stream=selected[0],
                min_score=0.85,
            )
        )

        assert (
            result["status"]
            == "ok"
        )

        assert (
            result["highlights"]
            == 1
        )

        assert (
            result["top_score"]
            == 0.91
        )

        assert (
            highlights
            == [expected]
        )

    finally:
        connection.close()