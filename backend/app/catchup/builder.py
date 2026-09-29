import sqlite3
from datetime import datetime

from app.catchup.descriptor import (
    StreamDescriptor,
    ImportantMomentDescriptor,
)
from app.event_pipeline.events import (
    DEFAULT_MERGE_GAP_MS,
    merge_highlights,
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


def build_stream_descriptor(
    connection: sqlite3.Connection,
    stream_id: str,
) -> StreamDescriptor | None:
    """
    将一场真实 Stream 压缩为
    Catch-up 输入层的基础 Descriptor。

    当前版本只生成：
    - metadata
    - duration
    - bv_ids

    important_moments 下一步再接。
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

    known_part_ends = [
        (int(part["start_offset_ms"]) + int(part["duration_ms"]))
        for part in parts
        if (part["duration_ms"] is not None)
    ]

    duration_ms = max(
        known_part_ends,
        default=None,
    )

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

    important_moments: list[ImportantMomentDescriptor] = []

    for candidate in candidates:
        source_highlights = [
            highlight_by_id[highlight_id]
            for highlight_id in candidate.source_highlight_ids
        ]

        salience_score = max(highlight.score for highlight in source_highlights)

        if salience_score < 0.95:
            continue

        part = part_by_id[candidate.part_id]

        offset_ms = int(part["start_offset_ms"])

        important_moments.append(
            ImportantMomentDescriptor(
                anchor_ms=(offset_ms + candidate.peak_ms),
                local_anchor_ms=(candidate.peak_ms),
                source_part_ids=[candidate.part_id],
                salience_score=(salience_score),
                source_highlight_ids=[highlight.id for highlight in source_highlights],
            )
        )

    return StreamDescriptor(
        stream_id=stream["id"],
        title=stream["title"],
        live_time=datetime.fromisoformat(
            stream["live_time"],
        ),
        duration_ms=duration_ms,
        bv_ids=stream["bv_ids"],
        important_moments=important_moments,
    )
