from dataclasses import dataclass
import sqlite3
from app.repository.highlight_repo import get_highlight_by_id
from app.repository.reaction_match_repo import list_reaction_matches_by_stream
from app.repository.stream_part_repo import list_stream_parts

MAX_REACTION_GAP_MS = 240_000
MAX_REACTION_MATCHES_PER_CANDIDATE = 6


@dataclass(frozen=True, slots=True)
class TopicCandidate:
    stream_id: str
    reaction_match_ids: list[str]
    source_part_ids: list[str]
    start_ms: int
    end_ms: int


def build_topic_candidates(
    connection: sqlite3.Connection, *, stream_id: str
) -> list[TopicCandidate]:
    matches = list_reaction_matches_by_stream(
        connection,
        stream_id=stream_id,
    )

    if not matches:
        return []

    parts = list_stream_parts(connection, stream_id)

    part_offsets = {part["part_id"]: part["start_offset_ms"] for part in parts}

    windows: list[tuple[str, str, int, int]] = []

    for match in matches:
        highlight = get_highlight_by_id(connection, match.highlight_id)

        if highlight is None:
            raise ValueError("missing highlight: " f"{match.highlight_id}")

        if match.part_id not in part_offsets:
            raise ValueError("missing StreamPart offset: " f"{match.part_id}")

        offset_ms = part_offsets[match.part_id]

        windows.append(
            (
                match.id,
                match.part_id,
                offset_ms + highlight.start_ms,
                offset_ms + highlight.end_ms,
            )
        )

    windows.sort(key=lambda item: (item[2], item[3]))

    candidates: list[TopicCandidate] = []

    current_match_ids: list[str] = []
    current_part_ids: list[str] = []

    current_start_ms = 0
    current_end_ms = 0

    for match_id, part_id, start_ms, end_ms in windows:
        if not current_match_ids:
            current_match_ids = [match_id]
            current_part_ids = [part_id]
            current_start_ms = start_ms
            current_end_ms = end_ms
            continue

        gap_ms = start_ms - current_end_ms

        can_join = (
            gap_ms <= MAX_REACTION_GAP_MS
            and len(current_match_ids) < MAX_REACTION_MATCHES_PER_CANDIDATE
        )

        if can_join:
            current_match_ids.append(match_id)

            if part_id not in current_part_ids:
                current_part_ids.append(part_id)

            current_end_ms = max(current_end_ms, end_ms)

            continue

        candidates.append(
            TopicCandidate(
                stream_id=stream_id,
                reaction_match_ids=(current_match_ids),
                source_part_ids=(current_part_ids),
                start_ms=current_start_ms,
                end_ms=current_end_ms,
            )
        )

        current_match_ids = [match_id]
        current_part_ids = [part_id]
        current_start_ms = start_ms
        current_end_ms = end_ms

    candidates.append(
        TopicCandidate(
            stream_id=stream_id,
            reaction_match_ids=(current_match_ids),
            source_part_ids=(current_part_ids),
            start_ms=current_start_ms,
            end_ms=current_end_ms,
        )
    )
    
    return candidates
