import sqlite3
from datetime import datetime

from app.domain.evidence.supplemental_evidence import SupplementalEvidence


def _validate_supplemental_evidence(
    connection: sqlite3.Connection,
    evidence: SupplementalEvidence,
) -> None:
    stream = connection.execute(
        "SELECT id FROM streams WHERE id = ?",
        (evidence.stream_id,),
    ).fetchone()
    if stream is None:
        raise ValueError(f"stream does not exist: {evidence.stream_id}")

    if evidence.topic_segment_id is not None:
        topic = connection.execute(
            "SELECT stream_id FROM topic_segments WHERE id = ?",
            (evidence.topic_segment_id,),
        ).fetchone()
        if topic is None:
            raise ValueError(f"topic segment does not exist: {evidence.topic_segment_id}")
        if topic[0] != evidence.stream_id:
            raise ValueError("topic segment does not belong to evidence stream")


def _row_to_evidence(row: tuple) -> SupplementalEvidence:
    return SupplementalEvidence(
        id=row[0],
        stream_id=row[1],
        topic_segment_id=row[2],
        source_type=row[3],
        content=row[4],
        source_url=row[5],
        created_at=datetime.fromisoformat(row[6]),
    )


def insert_supplemental_evidence(
    connection: sqlite3.Connection,
    evidence: SupplementalEvidence,
) -> None:
    _validate_supplemental_evidence(connection, evidence)

    with connection:
        connection.execute(
            """
            INSERT INTO supplemental_evidence (
                id, stream_id, topic_segment_id, source_type,
                content, source_url, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence.id,
                evidence.stream_id,
                evidence.topic_segment_id,
                evidence.source_type,
                evidence.content,
                evidence.source_url,
                evidence.created_at.isoformat(),
            ),
        )


def get_supplemental_evidence_by_id(
    connection: sqlite3.Connection,
    evidence_id: str,
) -> SupplementalEvidence | None:
    row = connection.execute(
        """
        SELECT id, stream_id, topic_segment_id, source_type,
               content, source_url, created_at
        FROM supplemental_evidence
        WHERE id = ?
        """,
        (evidence_id,),
    ).fetchone()
    return _row_to_evidence(row) if row is not None else None


def list_supplemental_evidence_by_stream(
    connection: sqlite3.Connection,
    *,
    stream_id: str,
) -> list[SupplementalEvidence]:
    rows = connection.execute(
        """
        SELECT id, stream_id, topic_segment_id, source_type,
               content, source_url, created_at
        FROM supplemental_evidence
        WHERE stream_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (stream_id,),
    ).fetchall()
    return [_row_to_evidence(row) for row in rows]
