import sqlite3
from datetime import datetime
from typing import Iterator
from uuid import UUID

import pytest

from app.domain.evidence.transcript_segment import TranscriptSegment
from app.domain.source.stream import Stream
from app.domain.source.stream_part import StreamPart
from app.domain.source.vtuber import Vtuber
from app.repository.database import init_db
from app.repository.stream_part_repo import insert_stream_part
from app.repository.stream_repo import insert_stream
from app.repository.transcript_segment_repo import (
    insert_transcript_segment,
    insert_transcript_segments_batch,
    list_transcript_segments_by_stream_part,
    list_transcript_segments_window,
)
from app.repository.vtuber_repo import insert_vtuber


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys = ON")
    try:
        init_db(db)
        insert_vtuber(db, Vtuber(id="aza", display_name="Aza"))
        insert_stream(
            db,
            Stream(
                id="stream-1",
                vtuber_id="aza",
                live_time=datetime(2026, 9, 20, 12, 0),
                title="测试直播",
            ),
        )
        for part_id in ("p0", "p1"):
            insert_stream_part(
                db,
                StreamPart(stream_id="stream-1", part_id=part_id),
            )
        yield db
    finally:
        db.close()


def make_segment(
    start_ms: int,
    end_ms: int,
    *,
    part_id: str = "p0",
) -> TranscriptSegment:
    return TranscriptSegment(
        stream_id="stream-1",
        part_id=part_id,
        start_ms=start_ms,
        end_ms=end_ms,
        raw_text=f"原始 {start_ms}",
        text=f"正文 {start_ms}",
        source="test_subtitle",
    )


def test_schema_and_time_index(connection: sqlite3.Connection) -> None:
    columns = {
        row[1]: row[2]
        for row in connection.execute("PRAGMA table_info(transcript_segments)")
    }
    assert columns == {
        "id": "TEXT",
        "stream_id": "TEXT",
        "part_id": "TEXT",
        "start_ms": "INTEGER",
        "end_ms": "INTEGER",
        "raw_text": "TEXT",
        "text": "TEXT",
        "source": "TEXT",
    }
    indexes = {
        row[1]
        for row in connection.execute("PRAGMA index_list(transcript_segments)")
    }
    assert "idx_transcript_segments_stream_part_time" in indexes
    indexed_columns = [
        row[2]
        for row in connection.execute(
            "PRAGMA index_info(idx_transcript_segments_stream_part_time)"
        )
    ]
    assert indexed_columns == ["stream_id", "part_id", "start_ms"]


def test_single_insert_round_trips_domain_id_and_all_fields(
    connection: sqlite3.Connection,
) -> None:
    segment = make_segment(1_250, 2_500)
    assert UUID(segment.id).version == 4

    insert_transcript_segment(connection, segment)

    row = connection.execute(
        """
        SELECT id, stream_id, part_id, start_ms, end_ms, raw_text, text, source
        FROM transcript_segments
        """
    ).fetchone()
    assert row == (
        segment.id,
        segment.stream_id,
        segment.part_id,
        segment.start_ms,
        segment.end_ms,
        segment.raw_text,
        segment.text,
        segment.source,
    )
    assert list_transcript_segments_by_stream_part(
        connection, stream_id="stream-1", part_id="p0"
    ) == [segment]


def test_batch_insert_sorts_by_start_then_end_and_isolates_parts(
    connection: sqlite3.Connection,
) -> None:
    later = make_segment(30, 40)
    longer = make_segment(10, 30)
    shorter = make_segment(10, 20)
    other_part = make_segment(5, 15, part_id="p1")
    insert_transcript_segments_batch(
        connection, [later, longer, other_part, shorter]
    )
    insert_transcript_segments_batch(connection, [])

    assert list_transcript_segments_by_stream_part(
        connection, stream_id="stream-1", part_id="p0"
    ) == [shorter, longer, later]
    assert list_transcript_segments_by_stream_part(
        connection, stream_id="stream-1", part_id="p1"
    ) == [other_part]
    assert list_transcript_segments_by_stream_part(
        connection, stream_id="another-stream", part_id="p0"
    ) == []


def test_window_uses_half_open_interval_overlap(
    connection: sqlite3.Connection,
) -> None:
    ends_at_start = make_segment(0, 10)
    crosses_start = make_segment(5, 11)
    covers_window = make_segment(0, 30)
    inside = make_segment(12, 18)
    crosses_end = make_segment(19, 30)
    starts_at_end = make_segment(20, 25)
    other_part = make_segment(12, 18, part_id="p1")
    insert_transcript_segments_batch(
        connection,
        [
            ends_at_start,
            crosses_start,
            covers_window,
            inside,
            crosses_end,
            starts_at_end,
            other_part,
        ],
    )

    assert list_transcript_segments_window(
        connection,
        stream_id="stream-1",
        part_id="p0",
        start_ms=10,
        end_ms=20,
    ) == [covers_window, crosses_start, inside, crosses_end]
    assert list_transcript_segments_window(
        connection,
        stream_id="stream-1",
        part_id="p1",
        start_ms=10,
        end_ms=20,
    ) == [other_part]


@pytest.mark.parametrize(
    ("start_ms", "end_ms"),
    [(-1, 10), (10, 10), (20, 10)],
)
def test_window_rejects_invalid_bounds(
    connection: sqlite3.Connection,
    start_ms: int,
    end_ms: int,
) -> None:
    with pytest.raises(ValueError):
        list_transcript_segments_window(
            connection,
            stream_id="stream-1",
            part_id="p0",
            start_ms=start_ms,
            end_ms=end_ms,
        )


def test_missing_stream_part_is_rejected_by_sqlite(
    connection: sqlite3.Connection,
) -> None:
    missing = make_segment(0, 10, part_id="missing")
    with pytest.raises(sqlite3.IntegrityError):
        insert_transcript_segment(connection, missing)
    assert list_transcript_segments_by_stream_part(
        connection, stream_id="stream-1", part_id="p0"
    ) == []


def test_deleting_stream_part_cascades_transcript_segments(
    connection: sqlite3.Connection,
) -> None:
    p0 = make_segment(0, 10)
    p1 = make_segment(0, 10, part_id="p1")
    insert_transcript_segments_batch(connection, [p0, p1])

    connection.execute(
        "DELETE FROM stream_parts WHERE stream_id = ? AND part_id = ?",
        ("stream-1", "p0"),
    )

    assert list_transcript_segments_by_stream_part(
        connection, stream_id="stream-1", part_id="p0"
    ) == []
    assert list_transcript_segments_by_stream_part(
        connection, stream_id="stream-1", part_id="p1"
    ) == [p1]
