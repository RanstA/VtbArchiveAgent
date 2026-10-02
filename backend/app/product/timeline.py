from pydantic import BaseModel, Field


class TimelineItem(BaseModel):
    """
    TimelineItem 表示一个 TopicSegment
    在产品时间线中的展示形式。

    TimelineItem 不重新进行语义判断，
    只展示已经由 TopicSegment 确定的信息。
    """

    topic_segment_id: str = Field(
        min_length=1,
        description="对应 TopicSegment 的稳定唯一标识",
    )

    stream_id: str = Field(
        min_length=1,
        description="关联所属 Stream 的稳定唯一标识",
    )

    start_ms: int = Field(
        ge=0,
        description="当前话题在整场 Stream 时间轴上的开始位置，单位毫秒",
    )

    end_ms: int = Field(
        ge=0,
        description="当前话题在整场 Stream 时间轴上的结束位置，单位毫秒",
    )

    title: str = Field(
        min_length=1,
        description="时间线展示使用的话题标题",
    )

    summary: str = Field(
        min_length=1,
        description="时间线展示使用的话题摘要",
    )

    keywords: list[str] = Field(
        description="当前话题的关键词",
    )

    entities: list[str] = Field(
        description="当前话题涉及的人物、作品、地点等实体",
    )

    salience_score: float = Field(
        ge=0.0,
        le=1.0,
        description="当前话题的显著程度，范围 [0,1]",
    )


class StreamTimeline(BaseModel):
    """
    StreamTimeline 表示一场 Stream 的完整话题时间线。

    items 由该 Stream 对应的 TimelineItem
    按 start_ms 从早到晚排列组成。
    """

    stream_id: str = Field(
        min_length=1,
        description="当前时间线所属 Stream 的稳定唯一标识",
    )

    items: list[TimelineItem] = Field(
        description="按 start_ms 排序后的时间线条目列表",
    )