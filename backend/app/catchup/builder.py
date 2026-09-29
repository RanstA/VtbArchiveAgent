import sqlite3
from datetime import datetime

from app.catchup.descriptor import (
    StreamDescriptor,
    ImportantMomentDescriptor,
)
from app.repository.stream_repo import (
    get_stream_by_id,
)
from app.event_pipeline.timeline import (
    build_stream_timeline,
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

    timeline = build_stream_timeline(
        connection=connection,
        stream_id=stream_id,
    )

    if timeline is None:
        return None

    important_moments = [
        ImportantMomentDescriptor(
            anchor_ms=(item.anchor_ms),
            local_anchor_ms=(item.local_anchor_ms),
            source_part_ids=(item.source_part_ids),
            salience_score=(item.salience_score),
            source_highlight_ids=(item.source_highlight_ids),
        )
        for item in timeline.items
        if item.salience_score >= 0.95
    ]

    return StreamDescriptor(
        stream_id=stream["id"],
        title=stream["title"],
        live_time=datetime.fromisoformat(
            stream["live_time"],
        ),
        duration_ms=timeline.duration_ms,
        bv_ids=stream["bv_ids"],
        important_moments=important_moments,
    )
