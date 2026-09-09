from datetime import datetime
from pathlib import Path

import pandas as pd

from app.domain.stream import Stream


def parse_publish_times(value: str) -> list[datetime]:
    if pd.isna(value):
        return []

    parts = str(value).split("|")

    return [
        pd.to_datetime(part.strip()).to_pydatetime()
        for part in parts
        if part.strip()
    ]


def load_streams(path: Path) -> list[Stream]:
    df = pd.read_csv(path)

    streams: list[Stream] = []

    for _, row in df.iterrows():
        stream = Stream(
            id=str(row["BV号"]),
            month=str(row["月份"]),
            live_time=pd.to_datetime(
                row["直播日期时间"]
            ).to_pydatetime(),
            publish_times=parse_publish_times(row["发布日期"]),
            bv_id=str(row["BV号"]),
            title=str(row["标题"]),
            video_url=str(row["视频链接"]),
            status=str(row["状态"]),
        )

        streams.append(stream)

    return streams