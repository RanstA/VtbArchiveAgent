import sqlite3

from app.event_pipeline.events import (
    DEFAULT_MERGE_GAP_MS,
    merge_highlights,
)
from app.repository.danmaku_repo import (
    list_danmaku_window,
)
from app.repository.highlight_repo import (
    list_highlights_by_stream,
)
from app.repository.stream_part_repo import (
    list_stream_parts,
)
from app.repository.stream_repo import (
    get_stream_by_id,
)
from app.domain.event import (
    Event,
)
from app.event_pipeline.semanticizer import (
    EventSemanticizer,
    EventSemanticizerInput,
)
from app.repository.event_repo import (
    upsert_event,
)


def build_semanticizer_inputs_for_stream(
    connection: sqlite3.Connection,
    stream_id: str,
    *,
    limit: int | None = None,
    danmaku_limit: int = 120,
) -> list[EventSemanticizerInput] | None:
    """
    为一场 Stream 构建 Event Semanticizer 输入。

    当前只负责：
        Stream metadata
        + Highlight Merge
        + local danmaku evidence
        -> EventSemanticizerInput

    不调用模型，也不写 Event。
    """

    if limit is not None and limit < 1:
        raise ValueError("limit must be >= 1")

    if danmaku_limit < 1:
        raise ValueError("danmaku_limit must be >= 1")

    stream = get_stream_by_id(
        connection=connection,
        stream_id=stream_id,
    )

    if stream is None:
        return None

    parts = list_stream_parts(
        connection=connection,
        stream_id=stream_id,
    )

    part_by_id = {part["part_id"]: part for part in parts}

    highlights = list_highlights_by_stream(
        connection=connection,
        stream_id=stream_id,
    )

    highlight_by_id = {highlight.id: highlight for highlight in highlights}

    candidates = merge_highlights(
        highlights,
        merge_gap_ms=(DEFAULT_MERGE_GAP_MS),
    )

    if limit is not None:
        candidates = candidates[:limit]

    inputs: list[EventSemanticizerInput] = []

    for candidate in candidates:
        part = part_by_id.get(candidate.part_id)

        if part is None:
            raise RuntimeError(
                "Event candidate references " "unknown part: " f"{candidate.part_id}"
            )

        danmaku_rows = list_danmaku_window(
            connection=connection,
            stream_id=stream_id,
            part_id=candidate.part_id,
            start_ms=candidate.start_ms,
            end_ms=candidate.end_ms,
            limit=danmaku_limit,
        )

        danmaku_texts = [row["text"] for row in danmaku_rows if row["text"].strip()]

        # EventSemanticizerInput 要求至少
        # 有一条 evidence。
        if not danmaku_texts:
            continue

        source_highlights = [
            highlight_by_id[highlight_id]
            for highlight_id in candidate.source_highlight_ids
        ]

        salience_score = max(highlight.score for highlight in source_highlights)

        inputs.append(
            EventSemanticizerInput(
                candidate=candidate,
                stream_title=(stream["title"]),
                danmaku_texts=(danmaku_texts),
                part_start_offset_ms=int(part["start_offset_ms"]),
                salience_score=(salience_score),
            )
        )

    return inputs


def semanticize_stream(
    connection: sqlite3.Connection,
    stream_id: str,
    *,
    semanticizer: EventSemanticizer,
    limit: int | None = None,
    danmaku_limit: int = 120,
) -> list[Event] | None:
    """
    对一场 Stream 的 EventCandidates
    执行语义化并持久化 Unified Events。

    模型通过 semanticizer 注入，
    因此这里不绑定具体模型提供商。
    """

    inputs = build_semanticizer_inputs_for_stream(
        connection=connection,
        stream_id=stream_id,
        limit=limit,
        danmaku_limit=danmaku_limit,
    )

    if inputs is None:
        return None

    events: list[Event] = []

    for semanticizer_input in inputs:
        event = semanticizer.semanticize(semanticizer_input)

        upsert_event(
            connection=connection,
            event=event,
        )

        events.append(event)

    return events
