from pydantic import BaseModel, Field


class Danmaku(BaseModel):
    """
    Danmaku 表示某个 StreamPart 中的一条弹幕记录。

    timestamp_ms 使用当前直播分段内的局部时间，
    而非整场直播时间。
    """

    id: int = Field(
        ge=1,
        description="系统内部唯一标识，用于 Evidence 引用",
    )

    stream_id: str = Field(min_length=1, description="关联所属 Stream 的稳定唯一标识")

    part_id: str = Field(
        min_length=1, description="关联所属 StreamPart，与 stream_id 共同定位直播分段"
    )

    timestamp_ms: int = Field(
        ge=0, description="弹幕在当前 Part 内出现的时间，单位毫秒"
    )

    raw_text: str = Field(
        description="从原始弹幕文件导入时读取到的文本，尽可能保留原始格式信息，用于数据追溯"
    )

    text: str = Field(description="去除 ASS 样式等格式后的纯文本内容，用于检索和分析")
