"""Read-only expansion of aggregate_evidence_windows() dictionaries."""

import sqlite3

from pydantic import BaseModel

from app.domain.evidence.danmaku import Danmaku
from app.domain.evidence.transcript_segment import TranscriptSegment
from app.repository.danmaku_repo import list_danmaku_window
from app.repository.transcript_segment_repo import list_transcript_segments_window


class SpeechEvidence(TranscriptSegment):
    """Persisted transcription, with its original Part-local range intact."""

    evidence_id: str
    stream_start_ms: int
    stream_end_ms: int
    is_seed: bool = False


class AudienceReactionEvidence(Danmaku):
    """A viewer message, never a statement of what the streamer did or said."""

    evidence_id: str
    # Danmaku does not persist importer provenance; do not infer ASS/XML/Bilibili.
    source: str | None = None
    stream_timestamp_ms: int
    is_seed: bool = False


class EvidenceContext(BaseModel):
    """Query-time projection; it is not a new persisted Domain entity."""

    stream_id: str
    part_id: str
    stream_title: str
    live_time: str
    start_offset_ms: int
    local_start_ms: int
    local_end_ms: int
    stream_start_ms: int
    stream_end_ms: int
    seed_evidence_ids: list[str]
    speech_evidence: list[SpeechEvidence]
    audience_reaction_evidence: list[AudienceReactionEvidence]


def expand_evidence_window(
    connection: sqlite3.Connection,
    window: dict,
    *,
    vtuber_id: str,
) -> EvidenceContext:
    """Expand one StreamPart only, and reject missing/stale/foreign seed refs."""
    vtuber_id = vtuber_id.strip()
    if not vtuber_id:
        raise ValueError("vtuber_id cannot be empty")
    stream_id, part_id = window["stream_id"], window["part_id"]
    row = connection.execute(
        """
        SELECT sp.start_offset_ms, s.title, s.live_time
        FROM stream_parts sp
        JOIN streams s ON s.id = sp.stream_id
        WHERE sp.stream_id = ? AND sp.part_id = ? AND s.vtuber_id = ?
        """,
        (stream_id, part_id, vtuber_id),
    ).fetchone()
    if row is None:
        raise ValueError("StreamPart does not exist in the requested VTuber workspace")
    offset, title, live_time = row
    start_ms, end_ms = window["local_start_ms"], window["local_end_ms"]
    if (
        type(start_ms) is not int or type(end_ms) is not int
        or start_ms < 0 or end_ms <= start_ms
    ):
        raise ValueError("invalid Part-local window bounds")
    if (
        window["stream_start_ms"] != offset + start_ms
        or window["stream_end_ms"] != offset + end_ms
    ):
        raise ValueError("window Stream-global offset does not match stored StreamPart")
    if not window["matches"]:
        raise ValueError("an investigation window must have seed evidence")

    transcripts = list_transcript_segments_window(
        connection, stream_id=stream_id, part_id=part_id,
        start_ms=start_ms, end_ms=end_ms,
    )
    # Select after reading the window: the repository's default first-120 limit
    # can otherwise silently exclude a late seed in a dense danmaku window.
    danmaku = list_danmaku_window(
        connection, stream_id=stream_id, part_id=part_id,
        start_ms=start_ms, end_ms=end_ms, limit=None,
    )
    speech: list[SpeechEvidence] = []
    for item in transcripts:
        if item.stream_id != stream_id or item.part_id != part_id:
            raise ValueError("transcript belongs to another StreamPart")
        speech.append(SpeechEvidence(
            **item.model_dump(), evidence_id=f"transcript:{item.id}",
            stream_start_ms=offset + item.start_ms,
            stream_end_ms=offset + item.end_ms,
        ))
    audience = [AudienceReactionEvidence(
        **item, stream_id=stream_id, part_id=part_id,
        evidence_id=f"danmaku:{item['id']}",
        stream_timestamp_ms=offset + item["timestamp_ms"],
    ) for item in danmaku]

    by_ref = {item.evidence_id: item for item in [*speech, *audience]}
    seed_ids: list[str] = []
    for match in window["matches"]:
        ref = match["evidence_id"]
        item = by_ref.get(ref)
        if item is None:
            raise ValueError(f"seed evidence missing from its StreamPart window: {ref}")
        if isinstance(item, SpeechEvidence):
            kind, local_start, local_end = "transcript", item.start_ms, item.end_ms
        else:
            kind, local_start, local_end = "danmaku", item.timestamp_ms, item.timestamp_ms + 1
        if (
            match["kind"] != kind
            or match["local_start_ms"] != local_start
            or match["local_end_ms"] != local_end
            or match["start_offset_ms"] != offset
            or local_start < start_ms or local_end > end_ms
        ):
            raise ValueError(f"seed evidence time/identity mismatch: {ref}")
        item.is_seed = True
        if ref not in seed_ids:
            seed_ids.append(ref)

    return EvidenceContext(
        stream_id=stream_id, part_id=part_id, stream_title=title, live_time=live_time,
        start_offset_ms=offset, local_start_ms=start_ms, local_end_ms=end_ms,
        stream_start_ms=offset + start_ms, stream_end_ms=offset + end_ms,
        seed_evidence_ids=seed_ids,
        speech_evidence=sorted(speech, key=lambda x: (x.start_ms, x.end_ms, x.id)),
        audience_reaction_evidence=sorted(audience, key=lambda x: (x.timestamp_ms, x.id)),
    )
