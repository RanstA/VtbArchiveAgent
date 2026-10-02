from pathlib import Path

import pandas as pd

from app.domain.source.stream import Stream, StreamStatus, make_stream_id


def load_streams(
    path: Path,
    *,
    vtuber_id: str,
) -> list[Stream]:
    """Load Source V1 Stream metadata from a legacy archive CSV."""
    vtuber_id = vtuber_id.strip()
    if not vtuber_id:
        raise ValueError("vtuber_id cannot be empty")

    df = pd.read_csv(path)
    streams: list[Stream] = []

    for _, row in df.iterrows():
        live_time = pd.to_datetime(row["直播日期时间"]).to_pydatetime()
        title = str(row["标题"]).strip()

        streams.append(
            Stream(
                id=make_stream_id(vtuber_id=vtuber_id, live_time=live_time),
                vtuber_id=vtuber_id,
                live_time=live_time,
                title=title,
                # CSV “状态”描述发布情况，不等于系统处理状态。
                status=StreamStatus.PENDING,
            )
        )

    return streams
