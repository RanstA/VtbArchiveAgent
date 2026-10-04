import sqlite3

from app.domain.evidence.transcript_segment import TranscriptSegment

_INSERT_SQL = """
    INSERT INTO transcript_segments (
        id,
        stream_id,
        part_id,
        start_ms,
        end_ms,
        raw_text,
        text,
        source
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""

_SELECT_COLUMNS = """
    id,
    stream_id,
    part_id,
    start_ms,
    end_ms,
    raw_text,
    text,
    source
"""


def _segment_values(segment: TranscriptSegment) -> tuple:
    return (
        segment.id,
        segment.stream_id,
        segment.part_id,
        segment.start_ms,
        segment.end_ms,
        segment.raw_text,
        segment.text,
        segment.source,
    )


def _row_to_segment(row: tuple) -> TranscriptSegment:
    return TranscriptSegment(
        id=row[0],
        stream_id=row[1],
        part_id=row[2],
        start_ms=row[3],
        end_ms=row[4],
        raw_text=row[5],
        text=row[6],
        source=row[7],
    )


def insert_transcript_segment(
    connection: sqlite3.Connection,
    segment: TranscriptSegment,
) -> None:
    connection.execute(_INSERT_SQL, _segment_values(segment))


def insert_transcript_segments_batch(
    connection: sqlite3.Connection,
    segments: list[TranscriptSegment],
) -> None:
    if not segments:
        return

    connection.executemany(
        _INSERT_SQL,
        [_segment_values(segment) for segment in segments],
    )


def list_transcript_segments_by_stream_part(
    connection: sqlite3.Connection,
    *,
    stream_id: str,
    part_id: str,
) -> list[TranscriptSegment]:
    rows = connection.execute(
        f"""
        SELECT {_SELECT_COLUMNS}
        FROM transcript_segments
        WHERE stream_id = ? AND part_id = ?
        ORDER BY start_ms ASC, end_ms ASC
        """,
        (stream_id, part_id),
    ).fetchall()
    return [_row_to_segment(row) for row in rows]


def list_transcript_segments_window(
    connection: sqlite3.Connection,
    *,
    stream_id: str,
    part_id: str,
    start_ms: int,
    end_ms: int,
) -> list[TranscriptSegment]:
    if start_ms < 0:
        raise ValueError("start_ms must be >= 0")
    if end_ms <= start_ms:
        raise ValueError("end_ms must be greater than start_ms")

    rows = connection.execute(
        f"""
        SELECT {_SELECT_COLUMNS}
        FROM transcript_segments
        WHERE stream_id = ?
          AND part_id = ?
          AND end_ms > ?
          AND start_ms < ?
        ORDER BY start_ms ASC, end_ms ASC
        """,
        (stream_id, part_id, start_ms, end_ms),
    ).fetchall()
    return [_row_to_segment(row) for row in rows]


def get_transcript_segments_by_ids(
    connection: sqlite3.Connection,
    *,
    transcript_segment_ids: list[str],
) -> list[TranscriptSegment]:
    if not transcript_segment_ids:
        return []

    placeholders = ",".join("?" for _ in transcript_segment_ids)

    rows = connection.execute(
        f"""
        SELECT
            id,
            stream_id,
            part_id,
            start_ms,
            end_ms,
            raw_text,
            text,
            source
        FROM transcript_segments
        WHERE id IN ({placeholders})
        """,
        transcript_segment_ids,
    ).fetchall()

    by_id = {
        row[0]: TranscriptSegment(
            id=row[0],
            stream_id=row[1],
            part_id=row[2],
            start_ms=row[3],
            end_ms=row[4],
            raw_text=row[5],
            text=row[6],
            source=row[7],
        )
        for row in rows
    }

    return [
        by_id[transcript_id]
        for transcript_id in transcript_segment_ids
        if transcript_id in by_id
    ]
