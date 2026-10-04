import sqlite3
from app.domain.signal.highlight import Highlight
from app.domain.pipeline.reaction_match import ReactionMatch
from app.repository.danmaku_repo import list_danmaku_window
from app.repository.highlight_repo import list_highlights_by_stream
from app.repository.reaction_match_repo import replace_reaction_matches_for_stream
from app.repository.transcript_segment_repo import list_transcript_segments_window

MATCHER_VERSION = "reaction_match_v0.1"

TRANSCRIPT_LOOKBACK_MS = 30_000
TRANSCRIPT_LOOKAHEAD_MS = 5_000


# @dataclass(frozen=True, slots=True)
# class DanmakuReactionGroup:
#     text: str
#     count: int
#     first_timestamp_ms: int
#     last_timestamp_ms: int


def _get_transcripts_for_highlight(
    connection: sqlite3.Connection,
    *,
    stream_id: str,
    part_id: str,
    highlight_start_ms: int,
    highlight_end_ms: int,
):
    start_ms = max(0, highlight_start_ms - TRANSCRIPT_LOOKBACK_MS)
    end_ms = highlight_end_ms + TRANSCRIPT_LOOKAHEAD_MS

    return list_transcript_segments_window(
        connection,
        stream_id=stream_id,
        part_id=part_id,
        start_ms=start_ms,
        end_ms=end_ms,
    )


def _get_danmaku_for_highlight(
    connection: sqlite3.Connection,
    *,
    stream_id: str,
    part_id: str,
    highlight_start_ms: int,
    highlight_end_ms: int,
):
    return list_danmaku_window(
        connection,
        stream_id=stream_id,
        part_id=part_id,
        start_ms=highlight_start_ms,
        end_ms=highlight_end_ms,
        limit=None,
    )


# def _normalize_danmaku_text(
#     text: str,
# ) -> str:
#     text = text.strip().lower()

#     # 去掉普通空格，
#     # 避免“哈 哈 哈”和“哈哈哈”
#     # 被认为是不同文本。
#     text = re.sub(r"\s+", "", text)

#     # 中文“哈”的连续重复。
#     text = re.sub(r"哈{2,}", "哈哈", text)

#     # 中文“啊”的连续重复。
#     text = re.sub(r"啊{2,}", "啊啊", text)

#     # 英文 hhh / HHH。
#     text = re.sub(r"h{2,}", "hh", text)

#     text = text.replace("？", "?").replace("！", "!")

#     text = re.sub(r"\?{2,}", "?", text)

#     text = re.sub(r"!{2,}", "!", text)

#     return text


# def _group_danmaku_reactions(danmaku: list[dict]) -> list[DanmakuReactionGroup]:
#     groups: dict[str, list[dict]] = {}
#     for item in danmaku:
#         normalized = _normalize_danmaku_text(item["text"])
#         if not normalized:
#             continue
#         groups.setdefault(normalized, []).append(item)
#     results: list[DanmakuReactionGroup] = []
#     for text, items in groups.items():
#         items.sort(key=lambda item: (item["timestamp_ms"], item["id"]))
#         results.append(
#             DanmakuReactionGroup(
#                 text=text,
#                 count=len(items),
#                 first_timestamp_ms=(items[0]["timestamp_ms"]),
#                 last_timestamp_ms=(items[-1]["timestamp_ms"]),
#             )
#         )

#     results.sort(
#         key=lambda group: (
#             -group.count,
#             group.first_timestamp_ms,
#         )
#     )

#     return results


def _build_one_reaction_match(
    connection: sqlite3.Connection, *, highlight: Highlight
) -> ReactionMatch | None:
    transcripts = _get_transcripts_for_highlight(
        connection=connection,
        stream_id=highlight.stream_id,
        part_id=highlight.part_id,
        highlight_start_ms=highlight.start_ms,
        highlight_end_ms=highlight.end_ms,
    )
    danmaku = _get_danmaku_for_highlight(
        connection,
        stream_id=highlight.stream_id,
        part_id=highlight.part_id,
        highlight_start_ms=highlight.start_ms,
        highlight_end_ms=highlight.end_ms,
    )
    if not transcripts or not danmaku:
        return None

    return ReactionMatch(
        stream_id=highlight.stream_id,
        part_id=highlight.part_id,
        highlight_id=highlight.id,
        transcript_segment_ids=[item.id for item in transcripts],
        danmaku_ids=[item["id"] for item in danmaku],
        matcher_version=MATCHER_VERSION,
    )



def build_reaction_matches(
    connection: sqlite3.Connection, *, stream_id: str
) -> list[ReactionMatch]:
    highlights = list_highlights_by_stream(connection, stream_id)
    matches: list[ReactionMatch] = []
    for highlight in highlights:
        match = _build_one_reaction_match(connection, highlight=highlight)
        if match is None:
            continue
        matches.append(match)
    replace_reaction_matches_for_stream(
        connection, stream_id=stream_id, reaction_matches=matches
    )
    return matches
