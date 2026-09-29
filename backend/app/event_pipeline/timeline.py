import sqlite3

from pydantic import (
    BaseModel,
    Field,
)

from app.domain.event import (
    make_event_id,
)
from app.event_pipeline.events import (
    DEFAULT_MERGE_GAP_MS,
    merge_highlights,
)
from app.repository.event_repo import (
    list_events_by_stream,
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


class TimelineItem(BaseModel):
    """
    一场 Stream 中用于产品层展示和消费的
    时间线节点。

    时间字段默认使用 Stream-global 时间。
    """

    id: str

    stream_id: str

    source_part_ids: list[str] = Field(
        min_length=1,
    )

    start_ms: int = Field(
        ge=0,
    )

    end_ms: int = Field(
        gt=0,
    )

    anchor_ms: int = Field(
        ge=0,
    )

    local_anchor_ms: int = Field(
        ge=0,
    )

    salience_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    # 可选语义字段。
    #
    # Highlight fallback 生成的 TimelineItem
    # 可以没有语义；
    #
    # Unified Event-backed Timeline
    # 会填充这些字段。
    title: str | None = None

    summary: str | None = None

    keywords: list[str] = Field(
        default_factory=list,
    )

    entities: list[str] = Field(
        default_factory=list,
    )

    # 通用证据引用。
    #
    # 当前 Unified Event 主要来自 Highlight，
    # 后续可以扩展到 Danmaku / ASR / VLM。
    evidence_refs: list[str] = Field(
        default_factory=list,
    )

    source_highlight_ids: list[str] = Field(
        default_factory=list,
    )


class StreamTimeline(BaseModel):
    """
    一场直播的统一 Timeline 结果。

    API / Catch-up / Agent
    后续统一消费这一层，
    不直接依赖底层 Event / Highlight
    构建算法。
    """

    stream_id: str

    duration_ms: int | None = Field(
        default=None,
        gt=0,
    )

    merge_gap_ms: int = Field(
        ge=0,
    )

    items: list[TimelineItem] = Field(
        default_factory=list,
    )


def build_stream_timeline(
    connection: sqlite3.Connection,
    stream_id: str,
) -> StreamTimeline | None:
    """
    为一场 Stream 构建统一 Timeline。

    优先级：

        Persisted Unified Event
        -> Timeline

    如果当前 Stream 还没有生成 Event：

        Highlight
        -> Merge
        -> Stream-global Timeline

    这样旧数据仍然可以正常工作，
    API / Catch-up / Agent 也无需知道
    Timeline 底层使用了哪种算法。
    """

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

    # ==========================================
    # 1. 优先使用持久化 Unified Events
    # ==========================================

    events = list_events_by_stream(
        connection=connection,
        stream_id=stream_id,
    )

    if events:
        part_by_id = {part["part_id"]: part for part in parts}

        items: list[TimelineItem] = []

        for event in events:
            anchor_part = None

            for part_id in event.source_part_ids:
                part = part_by_id.get(part_id)

                if part is None:
                    continue

                offset_ms = int(part["start_offset_ms"])

                duration_ms = (
                    int(part["duration_ms"])
                    if (part["duration_ms"] is not None)
                    else None
                )

                anchor_is_in_part = event.anchor_ms >= offset_ms and (
                    duration_ms is None or event.anchor_ms < (offset_ms + duration_ms)
                )

                if anchor_is_in_part:
                    anchor_part = part
                    break

            if anchor_part is None:
                raise RuntimeError(
                    "Event anchor does not " "belong to any source part: " f"{event.id}"
                )

            anchor_offset_ms = int(anchor_part["start_offset_ms"])

            items.append(
                TimelineItem(
                    id=event.id,
                    stream_id=(event.stream_id),
                    source_part_ids=(event.source_part_ids),
                    start_ms=(event.start_ms),
                    end_ms=(event.end_ms),
                    anchor_ms=(event.anchor_ms),
                    local_anchor_ms=(event.anchor_ms - anchor_offset_ms),
                    salience_score=(event.salience_score),
                    title=(event.title),
                    summary=(event.summary),
                    keywords=(event.keywords),
                    entities=(event.entities),
                    evidence_refs=[
                        ("highlight:" f"{highlight_id}")
                        for highlight_id in event.source_highlight_ids
                    ],
                    source_highlight_ids=(event.source_highlight_ids),
                )
            )

        items.sort(
            key=lambda item: (
                item.start_ms,
                item.end_ms,
            )
        )

        duration_ms = _compute_stream_duration(
            parts=parts,
            items=items,
        )

        return StreamTimeline(
            stream_id=stream_id,
            duration_ms=duration_ms,
            merge_gap_ms=(DEFAULT_MERGE_GAP_MS),
            items=items,
        )

    # ==========================================
    # 2. 没有 Unified Event 时，
    #    fallback 到旧 Highlight Timeline
    # ==========================================

    highlights = list_highlights_by_stream(
        connection=connection,
        stream_id=stream_id,
    )

    part_by_id = {part["part_id"]: part for part in parts}

    highlight_by_id = {highlight.id: highlight for highlight in highlights}

    candidates = merge_highlights(
        highlights,
        merge_gap_ms=(DEFAULT_MERGE_GAP_MS),
    )

    items: list[TimelineItem] = []

    for candidate in candidates:
        part = part_by_id.get(candidate.part_id)

        if part is None:
            raise RuntimeError(
                "Timeline candidate " "references unknown part: " f"{candidate.part_id}"
            )

        offset_ms = int(part["start_offset_ms"])

        start_ms = offset_ms + candidate.start_ms

        end_ms = offset_ms + candidate.end_ms

        anchor_ms = offset_ms + candidate.peak_ms

        source_highlights = [
            highlight_by_id[highlight_id]
            for highlight_id in candidate.source_highlight_ids
        ]

        salience_score = max(highlight.score for highlight in source_highlights)

        items.append(
            TimelineItem(
                id=make_event_id(
                    stream_id=stream_id,
                    start_ms=start_ms,
                    end_ms=end_ms,
                ),
                stream_id=stream_id,
                source_part_ids=[candidate.part_id],
                start_ms=start_ms,
                end_ms=end_ms,
                anchor_ms=anchor_ms,
                local_anchor_ms=(candidate.peak_ms),
                salience_score=(salience_score),
                source_highlight_ids=[highlight.id for highlight in source_highlights],
            )
        )

    items.sort(
        key=lambda item: (
            item.start_ms,
            item.end_ms,
        )
    )

    duration_ms = _compute_stream_duration(
        parts=parts,
        items=items,
    )

    return StreamTimeline(
        stream_id=stream_id,
        duration_ms=duration_ms,
        merge_gap_ms=(DEFAULT_MERGE_GAP_MS),
        items=items,
    )


def _compute_stream_duration(
    *,
    parts: list[dict],
    items: list[TimelineItem],
) -> int | None:
    """
    根据已知 Part duration 和 Timeline 末端
    推断整场 Stream duration。
    """

    known_part_ends = [
        (int(part["start_offset_ms"]) + int(part["duration_ms"]))
        for part in parts
        if (part["duration_ms"] is not None)
    ]

    timeline_end = max(
        (item.end_ms for item in items),
        default=0,
    )

    duration_ms = max(
        [
            *known_part_ends,
            timeline_end,
        ],
        default=0,
    )

    if duration_ms <= 0:
        return None

    return duration_ms
