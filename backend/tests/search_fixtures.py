"""Small persisted archives used only by the Search MVP tests."""

from datetime import datetime
import sqlite3

import pytest

from app.domain.evidence.transcript_segment import TranscriptSegment
from app.domain.pipeline.reaction_match import ReactionMatch
from app.domain.pipeline.topic_segment import TopicSegment
from app.domain.signal.highlight import Highlight
from app.domain.source.stream import Stream
from app.domain.source.stream_part import StreamPart
from app.domain.source.vtuber import Vtuber
from app.repository.danmaku_repo import insert_danmaku_batch
from app.repository.database import connect_db, init_db
from app.repository.highlight_repo import replace_highlights_for_stream
from app.repository.reaction_match_repo import insert_reaction_match
from app.repository.stream_part_repo import insert_stream_part
from app.repository.stream_repo import insert_stream
from app.repository.topic_segment_repo import insert_topic_segment
from app.repository.transcript_segment_repo import insert_transcript_segment
from app.repository.vtuber_repo import insert_vtuber


@pytest.fixture
def search_db(tmp_path):
    connection = connect_db(tmp_path / "search.db")
    try:
        init_db(connection)
        insert_vtuber(connection, Vtuber(id="aza", display_name="Aza"))
        insert_vtuber(connection, Vtuber(id="Izayoi161", display_name="十六萤"))
        for index, vtuber_id in enumerate(("aza", "aza", "Izayoi161"), start=1):
            stream_id = f"stream-{index}"
            insert_stream(connection, Stream(
                id=stream_id, vtuber_id=vtuber_id,
                live_time=datetime(2026, 10, index), title=f"直播 {index}",
            ))
            highlights = []
            matches = []
            for part_index in range(3):
                part_id = f"p{part_index}"
                prefix = f"{stream_id}-{part_id}"
                part_db_id = insert_stream_part(connection, StreamPart(
                    stream_id=stream_id, part_id=part_id,
                    start_offset_ms=part_index * 100_000, duration_ms=100_000,
                ))
                insert_danmaku_batch(connection, part_db_id, [
                    {"timestamp_ms": 1_500 + i * 1_000,
                     "raw_text": f"{{style}}弹幕 {i}", "text": f"弹幕 {i}"}
                    for i in range(3)
                ])
                danmaku_ids = [row[0] for row in connection.execute(
                    "SELECT id FROM danmaku WHERE stream_part_id = ? ORDER BY id",
                    (part_db_id,),
                )]
                transcript_ids = [f"{prefix}-t{i}" for i in range(2)]
                for i, transcript_id in enumerate(transcript_ids):
                    insert_transcript_segment(connection, TranscriptSegment(
                        id=transcript_id, stream_id=stream_id, part_id=part_id,
                        start_ms=1_000 + i * 2_000, end_ms=2_000 + i * 2_000,
                        raw_text=f" 原始转写 {i} ", text=f"转写 {i}", source="test",
                    ))
                for i, ids in enumerate((
                    [danmaku_ids[2], danmaku_ids[0]],
                    [danmaku_ids[0], danmaku_ids[1]],
                )):
                    highlight = Highlight(
                        id=f"{prefix}-h{i}", stream_id=stream_id, part_id=part_id,
                        start_ms=0, end_ms=30_000, peak_ms=2_000, score=0.9,
                        density_score=0.9, repetition_score=0.9, reaction_score=0.9,
                        reaction_ratio=0.5, danmaku_count=3, unique_text_count=3,
                        repetition_ratio=0, laugh_count=0, question_count=0,
                        exclamation_count=0, detector_version="test",
                    )
                    highlights.append(highlight)
                    matches.append(ReactionMatch(
                        id=f"{prefix}-m{i}", stream_id=stream_id, part_id=part_id,
                        highlight_id=highlight.id, transcript_segment_ids=transcript_ids,
                        danmaku_ids=ids, matcher_version="test",
                    ))
            replace_highlights_for_stream(connection, stream_id, highlights)
            for match in matches:
                insert_reaction_match(connection, match)
        connection.commit()
        yield connection
    finally:
        connection.close()


def seed_topic(
    connection: sqlite3.Connection,
    *,
    topic_id: str = "topic-1",
    stream_id: str = "stream-1",
    parts: tuple[str, ...] = ("p1",),
    start_ms: int = 101_000,
    title: str = "话题标题",
    summary: str = "话题摘要",
    keywords: list[str] | None = None,
    entities: list[str] | None = None,
) -> TopicSegment:
    topic = TopicSegment(
        id=topic_id, stream_id=stream_id, source_part_ids=list(parts),
        reaction_match_ids=[f"{stream_id}-{part}-m{i}" for part in parts for i in (0, 1)],
        start_ms=start_ms, end_ms=start_ms + 10_000,
        title=title, summary=summary, keywords=keywords or [], entities=entities or [],
        transcript_segment_ids=[f"{stream_id}-{part}-t{i}" for part in parts for i in (1, 0)],
        salience_score=0.9, confidence=0.8, analyzer_version="test", topic_type="talk",
    )
    insert_topic_segment(connection, topic)
    return topic
