import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.domain.stream import Stream, make_stream_id


def split_pipe(value) -> list[str]:
    if pd.isna(value):
        return []

    return [
        part.strip()
        for part in str(value).split("|")
        if part.strip()
    ]


def parse_publish_times(value) -> list[datetime]:
    if pd.isna(value):
        return []

    return [
        pd.to_datetime(part).to_pydatetime()
        for part in split_pipe(value)
    ]

def load_streams(
    path: Path,
    *,
    vtuber_id: str,
) -> list[Stream]:
    """
    从 CSV 加载某一个 Vtuber 的 Streams。
    """
    vtuber_id = vtuber_id.strip()
    if not vtuber_id:
        raise ValueError(
            "vtuber_id cannot be empty"
        )
    
    df = pd.read_csv(path)
    streams: list[Stream] = []
    
    for _, row in df.iterrows():
        live_time = pd.to_datetime(row["直播日期时间"]).to_pydatetime()

        title = str(row["标题"]).strip()
        
        stream = Stream(
            id = make_stream_id(
                vtuber_id=vtuber_id,
                live_time=live_time,
                title=title,
            ),
            vtuber_id=vtuber_id,
            month=str(row["月份"]),
            live_time=live_time,
            publish_times=parse_publish_times(row["发布日期"]),
            bv_ids=split_pipe(row["BV号"]),
            title=title,
            video_url=(
                ""
                if pd.isna(
                    row[
                        "视频链接"
                    ]
                )
                else str(
                    row[
                        "视频链接"
                    ]
                )
            ),
            status=str(
                row["状态"]
            ),
        )
        
        streams.append(stream)
        
    return streams


# def make_stream_id(
#     live_time: datetime,
#     title: str,
# ) -> str:
#     key = f"{live_time.isoformat()}|{title.strip()}"

#     return str(
#         uuid.uuid5(
#             uuid.NAMESPACE_URL,
#             key,
#         )
#     )


# def load_streams(path: Path) -> list[Stream]:
#     df = pd.read_csv(path)

#     streams: list[Stream] = []

#     for _, row in df.iterrows():
#         live_time = pd.to_datetime(
#             row["直播日期时间"]
#         ).to_pydatetime()

#         title = str(row["标题"]).strip()

#         stream = Stream(
#             id=make_stream_id(
#                 live_time=live_time,
#                 title=title,
#             ),
#             month=str(row["月份"]),
#             live_time=live_time,
#             publish_times=parse_publish_times(
#                 row["发布日期"]
#             ),
#             bv_ids=split_pipe(row["BV号"]),
#             title=title,
#             video_url=(
#                 ""
#                 if pd.isna(row["视频链接"])
#                 else str(row["视频链接"])
#             ),
#             status=str(row["状态"]),
#         )

#         streams.append(stream)

#     return streams