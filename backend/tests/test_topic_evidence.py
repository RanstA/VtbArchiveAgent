import pytest

from app.product import topic_evidence
from app.product.topic_evidence import (
    TopicEvidenceError,
    TopicNotFoundError,
    expand_topic_evidence,
)
from app.repository.danmaku_repo import get_danmaku_by_ids
from app.repository.reaction_match_repo import get_reaction_match_by_id
from app.repository.transcript_segment_repo import get_transcript_segments_by_ids
from search_fixtures import search_db, seed_topic


def test_evidence_expands_stored_refs_in_order_without_changing_local_times(search_db):
    topic = seed_topic(search_db, parts=("p1", "p0"))
    matches = [get_reaction_match_by_id(search_db, ref) for ref in topic.reaction_match_ids]
    expected_danmaku_ids = list(dict.fromkeys(
        ref for match in matches for ref in match.danmaku_ids
    ))
    before = search_db.total_changes
    bundle = expand_topic_evidence(search_db, topic.id)
    assert search_db.total_changes == before
    assert bundle.topic == topic
    assert [item.id for item in bundle.transcripts] == topic.transcript_segment_ids
    assert bundle.transcripts == get_transcript_segments_by_ids(
        search_db, transcript_segment_ids=topic.transcript_segment_ids,
    )
    assert [item.id for item in bundle.danmaku] == expected_danmaku_ids
    assert len(bundle.danmaku) == 6  # Shared representative IDs occur only once.
    assert bundle.danmaku == get_danmaku_by_ids(search_db, danmaku_ids=expected_danmaku_ids)
    assert bundle.topic.start_ms == 101_000  # Stream-global
    assert bundle.transcripts[0].part_id == "p1"
    assert (bundle.transcripts[0].start_ms, bundle.transcripts[0].end_ms) == (3_000, 4_000)
    assert bundle.transcripts[0].raw_text == " 原始转写 1 "
    assert bundle.transcripts[0].text == "转写 1"
    assert bundle.danmaku[0].timestamp_ms == 3_500
    assert bundle.danmaku[0].raw_text == "{style}弹幕 2"
    assert all(item.stream_id == topic.stream_id for item in [*bundle.transcripts, *bundle.danmaku])


def test_evidence_deduplicates_refs_without_mutating_topic(search_db, monkeypatch):
    topic = seed_topic(search_db)
    repeated = topic.model_copy(update={
        "transcript_segment_ids": topic.transcript_segment_ids + topic.transcript_segment_ids[:1],
        "reaction_match_ids": topic.reaction_match_ids + topic.reaction_match_ids[:1],
    })
    # The DB rejects duplicate links; exercise defensive expansion of a repeated input.
    monkeypatch.setattr(topic_evidence, "get_topic_segment_by_id", lambda *_: repeated)
    bundle = expand_topic_evidence(search_db, topic.id)
    assert [item.id for item in bundle.transcripts] == topic.transcript_segment_ids
    assert len(bundle.danmaku) == 3
    assert len(repeated.transcript_segment_ids) == 3
    assert len(repeated.reaction_match_ids) == 3


def test_only_topic_selected_transcripts_are_expanded(search_db):
    topic = seed_topic(search_db)
    search_db.execute(
        "DELETE FROM topic_segment_transcripts WHERE topic_segment_id = ? AND position = 1",
        (topic.id,),
    )
    bundle = expand_topic_evidence(search_db, topic.id)
    assert [item.id for item in bundle.transcripts] == topic.transcript_segment_ids[:1]


def test_missing_topic_fails_explicitly(search_db):
    with pytest.raises(TopicNotFoundError, match="TopicSegment not found: missing"):
        expand_topic_evidence(search_db, "missing")


@pytest.mark.parametrize("sql,message", [
    ("UPDATE topic_segment_reaction_matches SET reaction_match_id = 'missing' WHERE position = 0",
     "ReactionMatch not found: missing"),
    ("UPDATE topic_segment_transcripts SET transcript_segment_id = 'missing' WHERE position = 0",
     "TranscriptSegment not found: missing"),
    ("UPDATE reaction_match_danmaku SET danmaku_id = 999999 WHERE reaction_match_id = 'stream-1-p1-m0' AND position = 0",
     "Danmaku not found: 999999"),
])
def test_missing_refs_never_return_partial_evidence(search_db, sql, message):
    seed_topic(search_db)
    # Only this test DB is deliberately corrupted to emulate stale persisted refs.
    search_db.execute("PRAGMA foreign_keys = OFF")
    search_db.execute(sql)
    with pytest.raises(TopicEvidenceError, match=message):
        expand_topic_evidence(search_db, "topic-1")


@pytest.mark.parametrize("sql,message", [
    ("UPDATE reaction_matches SET stream_id = 'stream-3' WHERE id = 'stream-1-p1-m0'",
     "ReactionMatch StreamPart mismatch"),
    ("UPDATE reaction_matches SET part_id = 'p2' WHERE id = 'stream-1-p1-m0'",
     "ReactionMatch StreamPart mismatch"),
    ("UPDATE transcript_segments SET stream_id = 'stream-3' WHERE id = 'stream-1-p1-t1'",
     "TranscriptSegment StreamPart/reference mismatch"),
    ("UPDATE transcript_segments SET part_id = 'p2' WHERE id = 'stream-1-p1-t1'",
     "TranscriptSegment StreamPart/reference mismatch"),
    # p0 is in this topic, but the transcript and danmaku must still belong to their match's p1.
    ("UPDATE transcript_segments SET part_id = 'p0' WHERE id = 'stream-1-p1-t1'",
     "TranscriptSegment StreamPart/reference mismatch"),
    ("UPDATE danmaku SET stream_part_id = (SELECT id FROM stream_parts WHERE stream_id = 'stream-3' AND part_id = 'p1') WHERE id = (SELECT danmaku_id FROM reaction_match_danmaku WHERE reaction_match_id = 'stream-1-p1-m0' AND position = 0)",
     "Danmaku StreamPart mismatch"),
    ("UPDATE danmaku SET stream_part_id = (SELECT id FROM stream_parts WHERE stream_id = 'stream-1' AND part_id = 'p0') WHERE id = (SELECT danmaku_id FROM reaction_match_danmaku WHERE reaction_match_id = 'stream-1-p1-m0' AND position = 0)",
     "Danmaku StreamPart mismatch"),
    ("UPDATE topic_segment_parts SET part_id = 'missing' WHERE position = 0",
     "Invalid TopicSegment StreamPart refs"),
])
def test_evidence_rejects_wrong_stream_or_part(search_db, sql, message):
    seed_topic(search_db, parts=("p1", "p0"))
    search_db.execute(sql)
    with pytest.raises(TopicEvidenceError, match=message):
        expand_topic_evidence(search_db, "topic-1")


def test_transcript_must_be_supported_by_topic_reaction_matches(search_db):
    topic = seed_topic(search_db)
    search_db.execute(
        "DELETE FROM reaction_match_transcripts WHERE transcript_segment_id = ?",
        (topic.transcript_segment_ids[0],),
    )
    with pytest.raises(TopicEvidenceError, match="TranscriptSegment StreamPart/reference mismatch"):
        expand_topic_evidence(search_db, topic.id)


@pytest.mark.parametrize("sql,message", [
    ("DELETE FROM topic_segment_reaction_matches", "Invalid TopicSegment"),
    ("DELETE FROM topic_segment_transcripts", "Invalid TopicSegment"),
    ("DELETE FROM reaction_match_danmaku WHERE reaction_match_id = 'stream-1-p1-m0'", "Invalid ReactionMatch"),
])
def test_empty_required_links_fail_explicitly(search_db, sql, message):
    seed_topic(search_db)
    search_db.execute(sql)
    with pytest.raises(TopicEvidenceError, match=message):
        expand_topic_evidence(search_db, "topic-1")
