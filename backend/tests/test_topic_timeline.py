from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.config.settings import settings
from app.domain.evidence.transcript_segment import TranscriptSegment
from app.domain.pipeline.reaction_match import ReactionMatch
from app.domain.pipeline.topic_segment import TopicSegment
from app.domain.signal.highlight import Highlight
from app.domain.source.stream import Stream
from app.domain.source.stream_part import StreamPart
from app.domain.source.vtuber import Vtuber
from app.main import app
from app.product.timeline_builder import build_topic_segment_timeline
from app.repository.danmaku_repo import insert_danmaku_batch
from app.repository.database import connect_db, init_db
from app.repository.highlight_repo import replace_highlights_for_stream
from app.repository.reaction_match_repo import insert_reaction_match
from app.repository.stream_part_repo import insert_stream_part
from app.repository.stream_repo import insert_stream
from app.repository.topic_segment_repo import (
    insert_topic_segment,
    list_topic_segments_by_stream,
)
from app.repository.transcript_segment_repo import insert_transcript_segment
from app.repository.vtuber_repo import insert_vtuber


def _highlight(part_id: str, start_ms: int, peak_ms: int, score: float) -> Highlight:
    return Highlight(
        stream_id="stream-1",
        part_id=part_id,
        start_ms=start_ms,
        end_ms=start_ms + 30_000,
        peak_ms=peak_ms,
        score=score,
        density_score=score,
        repetition_score=score,
        reaction_score=score,
        reaction_ratio=0.5,
        danmaku_count=1,
        unique_text_count=1,
        repetition_ratio=0,
        laugh_count=0,
        question_count=0,
        exclamation_count=0,
        detector_version="test",
    )


def _prepare(db_path: Path) -> dict:
    connection = connect_db(db_path)
    try:
        init_db(connection)
        insert_vtuber(connection, Vtuber(id="aza", display_name="Aza"))
        insert_stream(
            connection,
            Stream(
                id="stream-1",
                vtuber_id="aza",
                live_time=datetime(2026, 9, 20, 12, 0),
                title="话题时间线测试",
            ),
        )
        p0_id = insert_stream_part(
            connection,
            StreamPart(
                stream_id="stream-1",
                part_id="p0",
                start_offset_ms=0,
                duration_ms=100_000,
            ),
        )
        p1_id = insert_stream_part(
            connection,
            StreamPart(
                stream_id="stream-1",
                part_id="p1",
                start_offset_ms=100_000,
                duration_ms=120_000,
            ),
        )
        for part_db_id in (p0_id, p1_id):
            insert_danmaku_batch(
                connection,
                part_db_id,
                [{"timestamp_ms": 1_000, "raw_text": "好", "text": "好"}],
            )
        danmaku_ids = [
            connection.execute(
                "SELECT id FROM danmaku WHERE stream_part_id = ?",
                (part_db_id,),
            ).fetchone()[0]
            for part_db_id in (p0_id, p1_id)
        ]
        transcripts = [
            TranscriptSegment(
                stream_id="stream-1",
                part_id=part_id,
                start_ms=1_000,
                end_ms=2_000,
                raw_text="原始字幕",
                text="字幕",
                source="test",
            )
            for part_id in ("p0", "p1")
        ]
        for transcript in transcripts:
            insert_transcript_segment(connection, transcript)

        highlights = [
            _highlight("p0", 20_000, 30_000, 0.70),
            _highlight("p1", 10_000, 25_000, 0.95),
            _highlight("p0", 50_000, 60_000, 0.95),
            _highlight("p1", 50_000, 70_000, 0.77),
        ]
        replace_highlights_for_stream(connection, "stream-1", highlights)
        reaction_matches = [
            ReactionMatch(
                stream_id="stream-1",
                part_id=highlight.part_id,
                highlight_id=highlight.id,
                transcript_segment_ids=[transcripts[part_index].id],
                danmaku_ids=[danmaku_ids[part_index]],
                matcher_version="test",
            )
            for highlight, part_index in zip(highlights, (0, 1, 0, 1))
        ]
        for reaction_match in reaction_matches:
            insert_reaction_match(connection, reaction_match)

        first = TopicSegment(
            stream_id="stream-1",
            source_part_ids=["p0", "p1"],
            reaction_match_ids=[item.id for item in reaction_matches[:3]],
            start_ms=20_000,
            end_ms=145_000,
            topic_type="talk",
            title="第一段话题",
            summary="来自已保存的话题摘要",
            keywords=["话题"],
            entities=["Aza"],
            transcript_segment_ids=[item.id for item in transcripts],
            salience_score=0.96,
            confidence=0.82,
            analyzer_version="test",
        )
        second = TopicSegment(
            stream_id="stream-1",
            source_part_ids=["p1"],
            reaction_match_ids=[reaction_matches[3].id],
            start_ms=150_000,
            end_ms=190_000,
            topic_type="interaction",
            title="第二段话题",
            summary="另一段摘要",
            keywords=[],
            entities=[],
            transcript_segment_ids=[transcripts[1].id],
            salience_score=0.77,
            confidence=0.8,
            analyzer_version="test",
        )
        # Insert in reverse order to verify the public timeline order.
        insert_topic_segment(connection, second)
        insert_topic_segment(connection, first)
        return {
            "first": first,
            "second": second,
            "highlights": highlights,
            "reaction_matches": reaction_matches,
            "transcripts": transcripts,
        }
    finally:
        connection.close()


def test_topic_timeline_api_projects_persisted_semantics_and_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "timeline.db"
    data = _prepare(db_path)
    monkeypatch.setattr(settings, "database_path", db_path)

    response = TestClient(app).get("/streams/stream-1/timeline")
    assert response.status_code == 200
    payload = response.json()
    assert payload["streamId"] == "stream-1"
    assert payload["durationMs"] == 220_000
    assert payload["mergeGapMs"] == 0
    assert [item["id"] for item in payload["items"]] == [
        data["first"].id,
        data["second"].id,
    ]

    first = payload["items"][0]
    assert first["streamId"] == "stream-1"
    assert first["sourcePartIds"] == ["p0", "p1"]
    assert (first["startMs"], first["endMs"]) == (20_000, 145_000)
    assert first["title"] == "第一段话题"
    assert first["summary"] == "来自已保存的话题摘要"
    assert first["keywords"] == ["话题"]
    assert first["entities"] == ["Aza"]
    assert first["salienceScore"] == 0.96
    assert first["topicType"] == "talk"
    assert first["sourceHighlightIds"] == [
        item.id for item in data["highlights"][:3]
    ]
    # p1 has a 100s Stream offset; score tie picks the earlier ReactionMatch.
    assert first["localAnchorMs"] == 25_000
    assert first["anchorMs"] == 125_000
    assert first["anchorMs"] != first["startMs"]
    assert first["evidenceRefs"] == [
        reference
        for reaction_match, highlight in zip(
            data["reaction_matches"][:3],
            data["highlights"][:3],
        )
        for reference in (
            f"reaction_match:{reaction_match.id}",
            f"highlight:{highlight.id}",
        )
    ] + [f"transcript:{item.id}" for item in data["transcripts"]]


def test_topic_timeline_sorts_and_uses_topic_end_when_part_duration_is_missing(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "timeline.db"
    data = _prepare(db_path)
    connection = connect_db(db_path)
    try:
        connection.execute(
            "UPDATE stream_parts SET duration_ms = NULL WHERE part_id = 'p1'"
        )
        timeline = build_topic_segment_timeline(
            connection,
            stream_id="stream-1",
            topic_segments=[data["second"], data["first"]],
        )
        assert [item.id for item in timeline.items] == [
            data["first"].id,
            data["second"].id,
        ]
        assert timeline.duration_ms == 190_000
    finally:
        connection.close()


@pytest.mark.parametrize("missing_table", [False, True])
def test_timeline_api_falls_back_when_no_topic_segments(
    tmp_path: Path,
    monkeypatch,
    missing_table: bool,
) -> None:
    db_path = tmp_path / "timeline.db"
    _prepare(db_path)
    connection = connect_db(db_path)
    try:
        connection.execute("DELETE FROM topic_segments")
        if missing_table:
            connection.execute("DROP TABLE topic_segments")
        connection.commit()
        if not missing_table:
            assert list_topic_segments_by_stream(
                connection,
                stream_id="stream-1",
            ) == []
    finally:
        connection.close()
    monkeypatch.setattr(settings, "database_path", db_path)

    response = TestClient(app).get("/streams/stream-1/timeline")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mergeGapMs"] == 20_000
    assert payload["items"]
    assert all(item["title"] is None for item in payload["items"])
