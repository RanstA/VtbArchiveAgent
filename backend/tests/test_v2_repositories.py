import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Iterator
from uuid import UUID

import pytest

from app.domain.evidence import SupplementalEvidence
from app.domain.pipeline import CorrectionProposal
from app.domain.source.stream import Stream
from app.domain.source.vtuber import Vtuber
from app.repository.correction_proposal_repo import (
    get_correction_proposal_by_id,
    insert_correction_proposal,
    list_correction_proposals_by_stream,
)
from app.repository.database import init_db
from app.repository.stream_repo import insert_stream
from app.repository.supplemental_evidence_repo import (
    get_supplemental_evidence_by_id,
    insert_supplemental_evidence,
    list_supplemental_evidence_by_stream,
)
from app.repository.vtuber_repo import insert_vtuber


CREATED_AT = datetime(2026, 10, 8, 20, 30, tzinfo=timezone(timedelta(hours=8)))


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys = ON")
    try:
        init_db(db)
        insert_vtuber(db, Vtuber(id="aza", display_name="Aza"))
        for stream_id in ("stream-1", "stream-2"):
            insert_stream(
                db,
                Stream(
                    id=stream_id,
                    vtuber_id="aza",
                    live_time=CREATED_AT,
                    title=f"直播 {stream_id}",
                ),
            )
            db.execute(
                """
                INSERT INTO topic_segments (
                    id, stream_id, start_ms, end_ms, topic_type,
                    title, summary, salience_score, confidence, analyzer_version
                ) VALUES (?, ?, 0, 1000, 'talk', '话题', '摘要', 0.8, 0.7, 'test')
                """,
                (f"topic-{stream_id[-1]}", stream_id),
            )
        db.commit()
        yield db
    finally:
        db.close()


def make_evidence(
    *,
    stream_id: str = "stream-1",
    topic_segment_id: str | None = None,
    created_at: datetime = CREATED_AT,
) -> SupplementalEvidence:
    return SupplementalEvidence(
        stream_id=stream_id,
        topic_segment_id=topic_segment_id,
        source_type="external_link",
        content="用户提供的资料",
        source_url="https://example.com/source",
        created_at=created_at,
    )


def make_proposal(
    evidence_ids: list[str],
    *,
    stream_id: str = "stream-1",
    target_type: str = "topic_segment",
    target_id: str = "topic-1",
) -> CorrectionProposal:
    return CorrectionProposal(
        stream_id=stream_id,
        target_type=target_type,
        target_id=target_id,
        supplemental_evidence_ids=evidence_ids,
        proposal="建议修改话题标题",
        reason="补充资料与现有标题不符",
        created_at=CREATED_AT,
    )


def test_supplemental_evidence_round_trip_and_stream_listing(
    connection: sqlite3.Connection,
) -> None:
    later = make_evidence(topic_segment_id="topic-1", created_at=CREATED_AT)
    earlier = make_evidence(created_at=CREATED_AT - timedelta(minutes=1))
    other = make_evidence(stream_id="stream-2")
    for evidence in (later, earlier, other):
        insert_supplemental_evidence(connection, evidence)

    assert get_supplemental_evidence_by_id(connection, later.id) == later
    assert get_supplemental_evidence_by_id(connection, "missing") is None
    assert list_supplemental_evidence_by_stream(
        connection, stream_id="stream-1"
    ) == [earlier, later]
    assert list_supplemental_evidence_by_stream(
        connection, stream_id="stream-2"
    ) == [other]
    assert UUID(later.id).version == 4


@pytest.mark.parametrize(
    "stream_id,topic_segment_id",
    [("missing", None), ("stream-1", "missing"), ("stream-1", "topic-2")],
)
def test_supplemental_evidence_rejects_invalid_relationships(
    connection: sqlite3.Connection,
    stream_id: str,
    topic_segment_id: str | None,
) -> None:
    evidence = make_evidence(stream_id=stream_id, topic_segment_id=topic_segment_id)
    with pytest.raises(ValueError):
        insert_supplemental_evidence(connection, evidence)
    assert get_supplemental_evidence_by_id(connection, evidence.id) is None


def test_topic_replacement_does_not_delete_supplemental_evidence(
    connection: sqlite3.Connection,
) -> None:
    evidence = make_evidence(topic_segment_id="topic-1")
    insert_supplemental_evidence(connection, evidence)
    connection.execute("DELETE FROM topic_segments WHERE id = 'topic-1'")
    connection.commit()
    persisted = get_supplemental_evidence_by_id(connection, evidence.id)
    assert persisted is not None
    assert persisted.topic_segment_id is None
    assert persisted.stream_id == "stream-1"


def test_correction_proposal_round_trip_preserves_evidence_order(
    connection: sqlite3.Connection,
) -> None:
    first = make_evidence()
    second = make_evidence(topic_segment_id="topic-1")
    insert_supplemental_evidence(connection, first)
    insert_supplemental_evidence(connection, second)

    proposal = make_proposal([second.id, first.id])
    insert_correction_proposal(connection, proposal)
    assert get_correction_proposal_by_id(connection, proposal.id) == proposal
    assert get_correction_proposal_by_id(connection, "missing") is None
    assert list_correction_proposals_by_stream(
        connection, stream_id="stream-1"
    ) == [proposal]
    assert list_correction_proposals_by_stream(
        connection, stream_id="stream-2"
    ) == []
    rows = connection.execute(
        """
        SELECT supplemental_evidence_id, position
        FROM correction_proposal_evidence
        WHERE correction_proposal_id = ?
        ORDER BY position ASC
        """,
        (proposal.id,),
    ).fetchall()
    assert rows == [(second.id, 0), (first.id, 1)]


def test_reviewed_proposal_datetime_round_trip(connection: sqlite3.Connection) -> None:
    evidence = make_evidence()
    insert_supplemental_evidence(connection, evidence)
    proposal = make_proposal([evidence.id], target_type="stream", target_id="stream-1")
    reviewed = proposal.model_copy(
        update={"status": "rejected", "reviewed_at": CREATED_AT, "review_note": "证据不足"}
    )
    insert_correction_proposal(connection, reviewed)
    assert get_correction_proposal_by_id(connection, reviewed.id) == reviewed


@pytest.mark.parametrize(
    "case",
    ["missing_stream", "wrong_stream_target", "missing_topic", "other_stream_topic",
     "missing_evidence", "other_stream_evidence"],
)
def test_correction_proposal_rejects_invalid_relationships(
    connection: sqlite3.Connection,
    case: str,
) -> None:
    own = make_evidence()
    other = make_evidence(stream_id="stream-2")
    insert_supplemental_evidence(connection, own)
    insert_supplemental_evidence(connection, other)
    proposal = {
        "missing_stream": lambda: make_proposal([own.id], stream_id="missing"),
        "wrong_stream_target": lambda: make_proposal(
            [own.id], target_type="stream", target_id="stream-2"
        ),
        "missing_topic": lambda: make_proposal([own.id], target_id="missing"),
        "other_stream_topic": lambda: make_proposal([own.id], target_id="topic-2"),
        "missing_evidence": lambda: make_proposal(["missing"]),
        "other_stream_evidence": lambda: make_proposal([other.id]),
    }[case]()
    with pytest.raises(ValueError):
        insert_correction_proposal(connection, proposal)
    assert get_correction_proposal_by_id(connection, proposal.id) is None


def test_v2_schema_is_additive_to_existing_v1_rows() -> None:
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys = ON")
    try:
        db.executescript(
            """
            CREATE TABLE vtubers (id TEXT PRIMARY KEY, display_name TEXT NOT NULL);
            CREATE TABLE streams (
                id TEXT PRIMARY KEY, vtuber_id TEXT NOT NULL,
                live_time TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL,
                FOREIGN KEY (vtuber_id) REFERENCES vtubers(id)
            );
            CREATE TABLE topic_segments (
                id TEXT PRIMARY KEY, stream_id TEXT NOT NULL,
                start_ms INTEGER NOT NULL, end_ms INTEGER NOT NULL,
                topic_type TEXT NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL,
                salience_score REAL NOT NULL, confidence REAL NOT NULL,
                analyzer_version TEXT NOT NULL,
                FOREIGN KEY (stream_id) REFERENCES streams(id)
            );
            INSERT INTO vtubers VALUES ('aza', 'Aza');
            INSERT INTO streams VALUES ('stream-1', 'aza', '2026-10-08T12:00:00', '原直播', '待处理');
            INSERT INTO topic_segments VALUES (
                'topic-1', 'stream-1', 0, 1000, 'talk', '原话题', '原摘要', 0.8, 0.7, 'v1'
            );
            """
        )
        init_db(db)
        init_db(db)
        assert db.execute("SELECT title FROM streams WHERE id = 'stream-1'").fetchone() == (
            "原直播",
        )
        assert db.execute(
            "SELECT title FROM topic_segments WHERE id = 'topic-1'"
        ).fetchone() == ("原话题",)
        tables = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {"supplemental_evidence", "correction_proposals", "correction_proposal_evidence"} <= tables
        assert "search_hits" not in tables
        indexes = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
        }
        assert "idx_supplemental_evidence_stream_created" in indexes
        assert "idx_correction_proposals_stream_created" in indexes
    finally:
        db.close()
