import sqlite3

import pytest

from app.domain.highlight import (
    Highlight,
    make_highlight_id,
)
from app.repository.database import (
    init_db,
)
from app.repository.highlight_repo import (
    get_highlight_by_id,
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


def insert_test_stream(
    connection: sqlite3.Connection,
    stream_id: str = "stream-1",
) -> None:
    connection.execute(
        """
        INSERT INTO vtubers (
            id,
            display_name
        )
        VALUES (?, ?)
        """,
        (
            "vtuber-test",
            "测试主播",
        ),
    )

    connection.execute(
        """
        INSERT INTO streams (
            id,
            vtuber_id,
            month,
            live_time,
            publish_times,
            title,
            video_url,
            status
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            stream_id,
            "vtuber-test",
            "2023-09",
            "2023-09-08T18:00:00+08:00",
            "[]",
            "测试直播",
            "",
            "ok",
        ),
    )

    connection.execute(
        """
        INSERT INTO stream_parts (
            stream_id,
            part_id,
            video_path,
            danmaku_path,
            xml_path
        )
        VALUES (
            ?, ?, ?, ?, ?
        )
        """,
        (
            stream_id,
            "p0",
            None,
            None,
            None,
        ),
    )

    connection.execute(
        """
        INSERT INTO stream_parts (
            stream_id,
            part_id,
            video_path,
            danmaku_path,
            xml_path
        )
        VALUES (
            ?, ?, ?, ?, ?
        )
        """,
        (
            stream_id,
            "p1",
            None,
            None,
            None,
        ),
    )

    connection.commit()


def make_highlight(
    stream_id: str = "stream-1",
    part_id: str = "p0",
    start_ms: int = 100_000,
    end_ms: int = 130_000,
    peak_ms: int = 115_000,
    score: float = 0.9,
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

        density_score=0.9,
        repetition_score=0.8,
        reaction_score=0.85,

        danmaku_count=100,
        unique_text_count=40,

        repetition_ratio=0.5,
        reaction_ratio=0.6,

        laugh_count=10,
        question_count=50,
        exclamation_count=5,

        detector_version="v0.1",
    )


def test_highlight_id_is_stable():
    first = make_highlight_id(
        stream_id="stream-1",
        part_id="p0",
        start_ms=100_000,
        end_ms=130_000,
    )

    second = make_highlight_id(
        stream_id="stream-1",
        part_id="p0",
        start_ms=100_000,
        end_ms=130_000,
    )

    assert first == second


def test_highlight_id_changes_when_window_changes():
    first = make_highlight_id(
        stream_id="stream-1",
        part_id="p0",
        start_ms=100_000,
        end_ms=130_000,
    )

    second = make_highlight_id(
        stream_id="stream-1",
        part_id="p0",
        start_ms=110_000,
        end_ms=140_000,
    )

    assert first != second


def test_same_time_in_different_parts_has_different_id():
    p0 = make_highlight_id(
        stream_id="stream-1",
        part_id="p0",
        start_ms=100_000,
        end_ms=130_000,
    )

    p1 = make_highlight_id(
        stream_id="stream-1",
        part_id="p1",
        start_ms=100_000,
        end_ms=130_000,
    )

    assert p0 != p1


def test_replace_highlights_for_stream():
    connection = make_connection()

    try:
        insert_test_stream(
            connection
        )

        first = make_highlight(
            start_ms=100_000,
            end_ms=130_000,
            peak_ms=115_000,
        )

        second = make_highlight(
            start_ms=200_000,
            end_ms=230_000,
            peak_ms=215_000,
        )

        replace_highlights_for_stream(
            connection=connection,
            stream_id="stream-1",
            highlights=[
                first,
                second,
            ],
        )

        stored = list_highlights_by_stream(
            connection=connection,
            stream_id="stream-1",
        )

        assert len(stored) == 2

        replacement = make_highlight(
            start_ms=300_000,
            end_ms=330_000,
            peak_ms=315_000,
        )

        replace_highlights_for_stream(
            connection=connection,
            stream_id="stream-1",
            highlights=[
                replacement,
            ],
        )

        stored = list_highlights_by_stream(
            connection=connection,
            stream_id="stream-1",
        )

        assert len(stored) == 1

        assert (
            stored[0].id
            == replacement.id
        )

    finally:
        connection.close()


def test_get_highlight_by_id():
    connection = make_connection()

    try:
        insert_test_stream(
            connection
        )

        highlight = make_highlight()

        replace_highlights_for_stream(
            connection=connection,
            stream_id="stream-1",
            highlights=[
                highlight,
            ],
        )

        stored = get_highlight_by_id(
            connection=connection,
            highlight_id=highlight.id,
        )

        assert stored is not None

        assert (
            stored.id
            == highlight.id
        )

        assert (
            stored.part_id
            == "p0"
        )

        assert (
            stored.detector_version
            == "v0.1"
        )

    finally:
        connection.close()


def test_replace_is_atomic_when_insert_fails():
    connection = make_connection()

    try:
        insert_test_stream(
            connection
        )

        original = make_highlight()

        replace_highlights_for_stream(
            connection=connection,
            stream_id="stream-1",
            highlights=[
                original,
            ],
        )

        invalid = make_highlight(
            part_id="p999",
            start_ms=200_000,
            end_ms=230_000,
            peak_ms=215_000,
        )

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            replace_highlights_for_stream(
                connection=connection,
                stream_id="stream-1",
                highlights=[
                    invalid,
                ],
            )

        stored = list_highlights_by_stream(
            connection=connection,
            stream_id="stream-1",
        )

        assert len(stored) == 1

        assert (
            stored[0].id
            == original.id
        )

    finally:
        connection.close()


def test_reject_highlight_from_other_stream():
    connection = make_connection()

    try:
        insert_test_stream(
            connection
        )

        other = make_highlight(
            stream_id="stream-2",
        )

        with pytest.raises(
            ValueError
        ):
            replace_highlights_for_stream(
                connection=connection,
                stream_id="stream-1",
                highlights=[
                    other,
                ],
            )

    finally:
        connection.close()