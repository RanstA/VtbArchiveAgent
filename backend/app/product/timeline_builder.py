"""Project persisted TopicSegments onto the existing Stream Timeline contract."""

import sqlite3
from dataclasses import dataclass

from app.domain.pipeline.topic_segment import TopicSegment
from app.repository.highlight_repo import get_highlight_by_id
from app.repository.reaction_match_repo import get_reaction_match_by_id
from app.repository.stream_part_repo import list_stream_parts
from app.repository.transcript_segment_repo import get_transcript_segments_by_ids


@dataclass(frozen=True)
class TopicTimelineItem:
    id: str
    stream_id: str
    source_part_ids: list[str]
    start_ms: int
    end_ms: int
    anchor_ms: int
    local_anchor_ms: int
    salience_score: float
    title: str
    summary: str
    keywords: list[str]
    entities: list[str]
    evidence_refs: list[str]
    source_highlight_ids: list[str]


@dataclass(frozen=True)
class TopicStreamTimeline:
    stream_id: str
    duration_ms: int | None
    merge_gap_ms: int
    items: list[TopicTimelineItem]


def build_topic_segment_timeline(
    connection: sqlite3.Connection,
    *,
    stream_id: str,
    topic_segments: list[TopicSegment],
) -> TopicStreamTimeline:
    """Only project stored semantics and traceable evidence; never infer new facts."""
    parts = list_stream_parts(connection, stream_id)
    parts_by_id = {part["part_id"]: part for part in parts}
    items: list[TopicTimelineItem] = []

    for topic in sorted(
        topic_segments,
        key=lambda item: (item.start_ms, item.end_ms, item.id),
    ):
        if topic.stream_id != stream_id:
            raise ValueError("topic segment belongs to another stream")

        source_highlight_ids: list[str] = []
        evidence_refs: list[str] = []
        anchor_highlight = None

        for reaction_match_id in topic.reaction_match_ids:
            reaction_match = get_reaction_match_by_id(connection, reaction_match_id)
            if (
                reaction_match is None
                or reaction_match.stream_id != stream_id
                or reaction_match.part_id not in topic.source_part_ids
            ):
                raise RuntimeError(f"invalid reaction match: {reaction_match_id}")

            highlight = get_highlight_by_id(connection, reaction_match.highlight_id)
            if (
                highlight is None
                or highlight.stream_id != stream_id
                or highlight.part_id != reaction_match.part_id
            ):
                raise RuntimeError(f"invalid highlight: {reaction_match.highlight_id}")

            source_highlight_ids.append(highlight.id)
            evidence_refs.extend(
                (f"reaction_match:{reaction_match.id}", f"highlight:{highlight.id}")
            )
            # Strict comparison keeps the first ReactionMatch on score ties.
            if anchor_highlight is None or highlight.score > anchor_highlight.score:
                anchor_highlight = highlight

        if anchor_highlight is None:
            raise RuntimeError(f"topic segment has no highlight: {topic.id}")

        part = parts_by_id.get(anchor_highlight.part_id)
        if part is None:
            raise RuntimeError(f"highlight references unknown part: {anchor_highlight.id}")

        transcripts = get_transcript_segments_by_ids(
            connection,
            transcript_segment_ids=topic.transcript_segment_ids,
        )
        if len(transcripts) != len(topic.transcript_segment_ids) or any(
            transcript.stream_id != stream_id
            or transcript.part_id not in topic.source_part_ids
            for transcript in transcripts
        ):
            raise RuntimeError(f"topic segment has invalid transcript refs: {topic.id}")
        evidence_refs.extend(f"transcript:{transcript.id}" for transcript in transcripts)

        items.append(
            TopicTimelineItem(
                id=topic.id,
                stream_id=topic.stream_id,
                source_part_ids=topic.source_part_ids,
                start_ms=topic.start_ms,
                end_ms=topic.end_ms,
                anchor_ms=int(part["start_offset_ms"]) + anchor_highlight.peak_ms,
                local_anchor_ms=anchor_highlight.peak_ms,
                salience_score=topic.salience_score,
                title=topic.title,
                summary=topic.summary,
                keywords=topic.keywords,
                entities=topic.entities,
                evidence_refs=evidence_refs,
                source_highlight_ids=source_highlight_ids,
            )
        )

    known_ends = [
        int(part["start_offset_ms"]) + int(part["duration_ms"])
        for part in parts
        if part["duration_ms"] is not None
    ]
    if parts and all(part["duration_ms"] is not None for part in parts):
        duration_ms = max(known_ends)
    else:
        duration_ms = max([*known_ends, *(item.end_ms for item in items)], default=0)

    return TopicStreamTimeline(
        stream_id=stream_id,
        duration_ms=duration_ms or None,
        # TopicSegments are already persisted; this projection does no merging.
        merge_gap_ms=0,
        items=items,
    )
