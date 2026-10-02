from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field
import uuid


def make_stream_id(vtuber_id: str, live_time: datetime) -> str:
    """
    根据主播 ID 和实际开播时间生成稳定的 Stream ID。
    同一个主播在同一个开播时间重复导入时，
    应始终得到相同的 Stream ID。
    """
    vtuber_id = vtuber_id.strip()
    if not vtuber_id:
        raise ValueError("vtuber_id cannot be empty")
    key = f"stream|" f"{vtuber_id}|" f"{live_time.isoformat()}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


class StreamStatus(StrEnum):
    PENDING = "待处理"
    INGESTED = "已导入"
    PROCESSED = "已处理"


class Stream(BaseModel):
    """
    Stream 表示一场逻辑直播。
    系统使用独立的 id 作为稳定标识，不直接使用 BV 号作为主键。
    一场 Stream 可以包含多个 StreamPart。
    """

    id: str = Field(min_length=1, description="系统内部稳定唯一标识")
    vtuber_id: str = Field(min_length=1, description="关联所属 Vtuber 的稳定唯一标识")
    live_time: datetime = Field(description="直播实际开始时间")
    title: str = Field(min_length=1, description="该场直播的统一标题")
    status: StreamStatus = Field(
        default=StreamStatus.PENDING, description="当前直播的数据处理状态"
    )
