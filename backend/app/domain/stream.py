from datetime import datetime

from pydantic import BaseModel


class Stream(BaseModel):
    # 系统内部稳定 ID，不再等于 BV
    id: str

    month: str
    live_time: datetime
    publish_times: list[datetime]

    # 一场直播可能对应多个 BV
    bv_ids: list[str]

    title: str
    video_url: str
    status: str