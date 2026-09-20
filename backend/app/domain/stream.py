import uuid
from datetime import datetime

from pydantic import BaseModel


def make_stream_id(
    vtuber_id: str,
    live_time: datetime,
    title: str,
) -> str:
    """
    生成稳定 Stream ID。

    Stream 身份由 vtuber + live time + title 共同确定。

    """

    vtuber_id = (
        vtuber_id.strip()
    )

    title = title.strip()

    if not vtuber_id:
        raise ValueError(
            "vtuber_id cannot be empty"
        )

    if not title:
        raise ValueError(
            "title cannot be empty"
        )

    key = (
        f"{vtuber_id}|"
        f"{live_time.isoformat()}|"
        f"{title}"
    )

    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            key,
        )
    )


class Stream(BaseModel):
    # 系统内部稳定 ID，
    # 不等于 BV。
    id: str

    # 所属主播。
    vtuber_id: str

    month: str

    live_time: datetime

    publish_times: list[
        datetime
    ]

    # 一场直播可能对应多个 BV。
    bv_ids: list[str]

    title: str

    video_url: str

    status: str