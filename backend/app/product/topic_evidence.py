
import sqlite3

from pydantic import BaseModel, ValidationError

from app.domain.pipeline.topic_segment import TopicSegment
from app.domain.evidence.transcript_segment import TranscriptSegment
from app.domain.evidence.danmaku import Danmaku

from app.repository.topic_segment_repo import get_topic_segment_by_id
from app.repository.reaction_match_repo import get_reaction_match_by_id
from app.repository.transcript_segment_repo import get_transcript_segments_by_ids
from app.repository.danmaku_repo import get_danmaku_by_ids
from app.repository.stream_part_repo import list_stream_parts


class TopicNotFoundError(ValueError):
    """The requested topic does not exist."""


class TopicEvidenceError(ValueError):
    """Stored evidence references are incomplete or inconsistent."""


class TopicEvidenceBundle(BaseModel):
    topic: TopicSegment
    transcripts: list[TranscriptSegment]
    danmaku: list[Danmaku]


def expand_topic_evidence(
    connection: sqlite3.Connection,
    topic_segment_id: str,
) -> TopicEvidenceBundle:
    """Expand persisted references in their original order; times stay Part-local."""
    try:
        topic = get_topic_segment_by_id(connection, topic_segment_id)
    except ValidationError as exc:
        raise TopicEvidenceError(
            f"Invalid TopicSegment or evidence references: {topic_segment_id}"
        ) from exc

    if topic is None:
        raise TopicNotFoundError(f"TopicSegment not found: {topic_segment_id}")

    available_parts = {
        part["part_id"] for part in list_stream_parts(connection, topic.stream_id)
    }
    if not set(topic.source_part_ids) <= available_parts:
        raise TopicEvidenceError(f"Invalid TopicSegment StreamPart refs: {topic.id}")

    danmaku_ids: list[int] = []
    matches = []
    transcript_parts: dict[str, set[str]] = {}

    for match_id in dict.fromkeys(topic.reaction_match_ids):
        try:
            match = get_reaction_match_by_id(connection, match_id)
        except ValidationError as exc:
            raise TopicEvidenceError(
                f"Invalid ReactionMatch or evidence references: {match_id}"
            ) from exc

        if match is None:
            raise TopicEvidenceError(f"ReactionMatch not found: {match_id}")
        if (
            match.stream_id != topic.stream_id
            or match.part_id not in topic.source_part_ids
        ):
            raise TopicEvidenceError(f"ReactionMatch StreamPart mismatch: {match_id}")

        matches.append(match)
        for transcript_id in match.transcript_segment_ids:
            transcript_parts.setdefault(transcript_id, set()).add(match.part_id)
        danmaku_ids.extend(match.danmaku_ids)

    # 按原有顺序去重
    transcript_ids = list(dict.fromkeys(topic.transcript_segment_ids))
    danmaku_ids = list(dict.fromkeys(danmaku_ids))

    try:
        transcripts = get_transcript_segments_by_ids(
            connection,
            transcript_segment_ids=transcript_ids,
        )
        danmaku = get_danmaku_by_ids(connection, danmaku_ids=danmaku_ids)
    except ValidationError as exc:
        raise TopicEvidenceError(f"Invalid stored Evidence for topic: {topic.id}") from exc

    transcripts_by_id = {item.id: item for item in transcripts}
    danmaku_by_id = {item.id: item for item in danmaku}
    for transcript_id in transcript_ids:
        transcript = transcripts_by_id.get(transcript_id)
        if transcript is None:
            raise TopicEvidenceError(f"TranscriptSegment not found: {transcript_id}")
        if (
            transcript.stream_id != topic.stream_id
            or transcript.part_id not in topic.source_part_ids
            or transcript_parts.get(transcript_id) != {transcript.part_id}
        ):
            raise TopicEvidenceError(
                f"TranscriptSegment StreamPart/reference mismatch: {transcript_id}"
            )

    # Check against each referring match, even when an ID was already encountered.
    for match in matches:
        for danmaku_id in match.danmaku_ids:
            item = danmaku_by_id.get(danmaku_id)
            if item is None:
                raise TopicEvidenceError(f"Danmaku not found: {danmaku_id}")
            if item.stream_id != topic.stream_id or item.part_id != match.part_id:
                raise TopicEvidenceError(f"Danmaku StreamPart mismatch: {danmaku_id}")

    return TopicEvidenceBundle(
        topic=topic,
        transcripts=[transcripts_by_id[item_id] for item_id in transcript_ids],
        danmaku=[danmaku_by_id[item_id] for item_id in danmaku_ids],
    )
