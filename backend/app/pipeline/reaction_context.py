from dataclasses import dataclass
import re
import sqlite3

from app.domain.pipeline.reaction_match import ReactionMatch
from app.repository.danmaku_repo import get_danmaku_by_ids
from app.repository.transcript_segment_repo import get_transcript_segments_by_ids
from app.domain.evidence.danmaku import Danmaku
from app.domain.evidence.transcript_segment import TranscriptSegment


@dataclass(frozen=True, slots=True)
class DanmakuReactionGroup:
    text: str
    count: int
    first_timestamp_ms: int
    last_timestamp_ms: int


@dataclass(frozen=True, slots=True)
class ReactionContext:
    reaction_match_id: str
    highlight_id: str
    stream_id: str
    part_id: str

    transcripts: list[TranscriptSegment]
    reaction_groups: list[DanmakuReactionGroup]

    raw_danmaku_count: int


def _normalize_danmaku_text(text: str) -> str:
    text = text.strip().lower()

    text = re.sub(r"\s+", "", text)

    text = re.sub(r"哈{2,}", "哈哈", text)

    text = re.sub(r"啊{2,}", "啊啊", text)

    text = re.sub(r"h{2,}", "hh", text)

    text = text.replace("？", "?").replace("！", "!")

    text = re.sub(r"\?{2,}", "?", text)

    text = re.sub(r"!{2,}", "!", text)

    return text


def _group_danmaku_reactions(
    danmaku: list[Danmaku],
) -> list[DanmakuReactionGroup]:
    groups: dict[
        str,
        list[Danmaku],
    ] = {}

    for item in danmaku:
        normalized = _normalize_danmaku_text(item.text)

        if not normalized:
            continue

        groups.setdefault(
            normalized,
            [],
        ).append(item)

    results: list[DanmakuReactionGroup] = []

    for text, items in groups.items():
        items.sort(
            key=lambda item: (
                item.timestamp_ms,
                item.id,
            )
        )

        results.append(
            DanmakuReactionGroup(
                text=text,
                count=len(items),
                first_timestamp_ms=(items[0].timestamp_ms),
                last_timestamp_ms=(items[-1].timestamp_ms),
            )
        )

    results.sort(
        key=lambda group: (
            -group.count,
            group.first_timestamp_ms,
        )
    )

    return results


def build_reaction_context(
    connection: sqlite3.Connection,
    *,
    reaction_match: ReactionMatch,
) -> ReactionContext:
    transcripts = get_transcript_segments_by_ids(
        connection,
        transcript_segment_ids=(reaction_match.transcript_segment_ids),
    )

    danmaku = get_danmaku_by_ids(
        connection,
        danmaku_ids=reaction_match.danmaku_ids,
    )

    if len(transcripts) != len(reaction_match.transcript_segment_ids):
        raise ValueError("failed to restore all " "transcript evidence")

    if len(danmaku) != len(reaction_match.danmaku_ids):
        raise ValueError("failed to restore all " "danmaku evidence")

    reaction_groups = _group_danmaku_reactions(danmaku)

    return ReactionContext(
        reaction_match_id=reaction_match.id,
        highlight_id=reaction_match.highlight_id,
        stream_id=reaction_match.stream_id,
        part_id=reaction_match.part_id,
        transcripts=transcripts,
        reaction_groups=reaction_groups,
        raw_danmaku_count=len(danmaku),
    )
