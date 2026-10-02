from pydantic import BaseModel, Field

from app.domain.signal.highlight import Highlight


DEFAULT_MERGE_GAP_MS = 20_000
DEFAULT_MAX_EVENT_DURATION_MS = 120_000


class EventCandidate(BaseModel):
    """
    Highlight Merge 后、Semanticizer 前的中间产物。

    它只描述 Event 的结构边界，
    不包含 title / summary / keywords 等语义字段。
    """

    stream_id: str
    part_id: str

    start_ms: int = Field(
        ge=0
    )

    end_ms: int = Field(
        gt=0
    )

    peak_ms: int = Field(
        ge=0
    )

    source_highlight_ids: list[str] = Field(
        min_length=1
    )


def merge_highlights(
    highlights: list[Highlight],
    *,
    merge_gap_ms: int = DEFAULT_MERGE_GAP_MS,
    max_event_duration_ms: int = DEFAULT_MAX_EVENT_DURATION_MS,
) -> list[EventCandidate]:
    """
    将时间上连续或接近的 Highlight
    合并为 EventCandidate。
    """

    if merge_gap_ms < 0:
        raise ValueError(
            "merge_gap_ms must be >= 0"
        )

    if max_event_duration_ms <= 0:
        raise ValueError(
            "max_event_duration_ms must be > 0"
        )

    if not highlights:
        return []

    ordered = sorted(
        highlights,
        key=lambda item: (
            item.stream_id,
            item.part_id,
            item.start_ms,
        ),
    )

    groups: list[list[Highlight]] = []

    current_group: list[Highlight] = [
        ordered[0]
    ]

    for highlight in ordered[1:]:
        previous = current_group[-1]

        same_stream = (
            highlight.stream_id
            == previous.stream_id
        )

        same_part = (
            highlight.part_id
            == previous.part_id
        )

        close_enough = (
            highlight.start_ms
            <= previous.end_ms
            + merge_gap_ms
        )

        candidate_start_ms = (
            current_group[0].start_ms
        )

        duration_ok = (
            highlight.end_ms
            - candidate_start_ms
            <= max_event_duration_ms
        )

        if (
            same_stream
            and same_part
            and close_enough
            and duration_ok
        ):
            current_group.append(
                highlight
            )
        else:
            groups.append(
                current_group
            )

            current_group = [
                highlight
            ]

    groups.append(
        current_group
    )

    candidates: list[
        EventCandidate
    ] = []

    for group in groups:
        peak_highlight = max(
            group,
            key=lambda item: item.score,
        )

        candidates.append(
            EventCandidate(
                stream_id=group[0].stream_id,
                part_id=group[0].part_id,
                start_ms=min(
                    item.start_ms
                    for item in group
                ),
                end_ms=max(
                    item.end_ms
                    for item in group
                ),
                peak_ms=(
                    peak_highlight.peak_ms
                ),
                source_highlight_ids=[
                    item.id
                    for item in group
                ],
            )
        )

    return candidates
