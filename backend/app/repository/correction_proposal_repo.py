import sqlite3
from datetime import datetime

from app.domain.pipeline.correction_proposal import CorrectionProposal


def _validate_correction_proposal(
    connection: sqlite3.Connection,
    proposal: CorrectionProposal,
) -> None:
    stream = connection.execute(
        "SELECT id FROM streams WHERE id = ?",
        (proposal.stream_id,),
    ).fetchone()
    if stream is None:
        raise ValueError(f"stream does not exist: {proposal.stream_id}")

    if proposal.target_type == "stream":
        if proposal.target_id != proposal.stream_id:
            raise ValueError("stream target_id must equal stream_id")
    elif proposal.target_type == "topic_segment":
        topic = connection.execute(
            "SELECT stream_id FROM topic_segments WHERE id = ?",
            (proposal.target_id,),
        ).fetchone()
        if topic is None:
            raise ValueError(f"topic segment does not exist: {proposal.target_id}")
        if topic[0] != proposal.stream_id:
            raise ValueError("target topic segment belongs to another stream")
    else:
        raise ValueError(f"unsupported target_type: {proposal.target_type}")

    evidence_ids = proposal.supplemental_evidence_ids
    if not evidence_ids or len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("supplemental_evidence_ids must be unique and nonempty")

    for evidence_id in evidence_ids:
        evidence = connection.execute(
            "SELECT stream_id FROM supplemental_evidence WHERE id = ?",
            (evidence_id,),
        ).fetchone()
        if evidence is None:
            raise ValueError(f"supplemental evidence does not exist: {evidence_id}")
        if evidence[0] != proposal.stream_id:
            raise ValueError("supplemental evidence belongs to another stream")


def _row_to_proposal(row: tuple, evidence_ids: list[str]) -> CorrectionProposal:
    return CorrectionProposal(
        id=row[0],
        stream_id=row[1],
        target_type=row[2],
        target_id=row[3],
        supplemental_evidence_ids=evidence_ids,
        proposal=row[4],
        reason=row[5],
        status=row[6],
        created_at=datetime.fromisoformat(row[7]),
        reviewed_at=datetime.fromisoformat(row[8]) if row[8] is not None else None,
        review_note=row[9],
    )


def insert_correction_proposal(
    connection: sqlite3.Connection,
    proposal: CorrectionProposal,
) -> None:
    _validate_correction_proposal(connection, proposal)

    with connection:
        connection.execute(
            """
            INSERT INTO correction_proposals (
                id, stream_id, target_type, target_id, proposal,
                reason, status, created_at, reviewed_at, review_note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal.id,
                proposal.stream_id,
                proposal.target_type,
                proposal.target_id,
                proposal.proposal,
                proposal.reason,
                proposal.status,
                proposal.created_at.isoformat(),
                proposal.reviewed_at.isoformat() if proposal.reviewed_at else None,
                proposal.review_note,
            ),
        )
        connection.executemany(
            """
            INSERT INTO correction_proposal_evidence (
                correction_proposal_id, supplemental_evidence_id, position
            ) VALUES (?, ?, ?)
            """,
            [
                (proposal.id, evidence_id, position)
                for position, evidence_id in enumerate(proposal.supplemental_evidence_ids)
            ],
        )


def get_correction_proposal_by_id(
    connection: sqlite3.Connection,
    proposal_id: str,
) -> CorrectionProposal | None:
    row = connection.execute(
        """
        SELECT id, stream_id, target_type, target_id, proposal,
               reason, status, created_at, reviewed_at, review_note
        FROM correction_proposals
        WHERE id = ?
        """,
        (proposal_id,),
    ).fetchone()
    if row is None:
        return None

    evidence_rows = connection.execute(
        """
        SELECT supplemental_evidence_id
        FROM correction_proposal_evidence
        WHERE correction_proposal_id = ?
        ORDER BY position ASC
        """,
        (proposal_id,),
    ).fetchall()
    return _row_to_proposal(row, [item[0] for item in evidence_rows])


def list_correction_proposals_by_stream(
    connection: sqlite3.Connection,
    *,
    stream_id: str,
) -> list[CorrectionProposal]:
    rows = connection.execute(
        """
        SELECT id
        FROM correction_proposals
        WHERE stream_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (stream_id,),
    ).fetchall()
    return [
        proposal
        for row in rows
        if (proposal := get_correction_proposal_by_id(connection, row[0])) is not None
    ]
