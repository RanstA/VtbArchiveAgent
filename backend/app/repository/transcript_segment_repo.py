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



def search_transcripts_for_vtuber(
    connection: sqlite3.Connection,
    *,
    vtuber_id: str,
    query: str,
    limit: int = 20,
) -> list[dict]:
    """Search persisted transcripts, including those outside TopicSegments."""
    term = query.strip()
    vtuber_id = vtuber_id.strip()

    if not vtuber_id:
        raise ValueError("vtuber_id cannot be empty")
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    if not term:
        return []

    rows = connection.execute(
        """
        SELECT
            ts.id, ts.stream_id, ts.part_id,
            ts.start_ms, ts.end_ms,
            ts.text, ts.source,
            sp.start_offset_ms,
            s.title, s.live_time
        FROM transcript_segments ts
        JOIN streams s
            ON s.id = ts.stream_id
        JOIN stream_parts sp
            ON sp.stream_id = ts.stream_id
            AND sp.part_id = ts.part_id
        WHERE s.vtuber_id = ?
            AND instr(ts.text, ?) > 0
        ORDER BY
            s.live_time DESC,
            sp.start_offset_ms + ts.start_ms ASC,
            ts.id ASC
        LIMIT ?
        """,
        (vtuber_id, term, limit),
    ).fetchall()

    return [
        {
            "evidence_id": f"transcript:{r[0]}",
            "stream_id": r[1],
            "part_id": r[2],
            "start_ms": r[3],
            "end_ms": r[4],
            "text": r[5],
            "source": r[6],
            "stream_start_ms": r[7] + r[3],
            "stream_end_ms": r[7] + r[4],
            "stream_title": r[8],
            "live_time": r[9],
        }
        for r in rows
    ]
