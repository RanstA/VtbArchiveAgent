import uuid
from typing import Literal
from pydantic import BaseModel, Field, model_validator

TopicType = Literal[
    "talk",
    "interaction",
    "singing",
    "gameplay",
    "reaction",
    "announcement",
]

def make_topic_segment_id() -> str:
    """
    生成系统内部稳定的 TopicSegment ID。
    创建后应持久化保存，不重新生成。
    """
    return str(uuid.uuid4())


class TopicSegment(BaseModel):
    """
    TopicSegment 表示系统根据一组时间相近的 ReactionMatch
    及其相关转写内容，经过话题分析后形成的完整语义话题片段。

    start_ms 与 end_ms 使用整场 Stream 时间轴，
    而不是单个 StreamPart 内的局部时间。

    一个 TopicSegment 可以跨越多个 StreamPart。
    """

    id: str = Field(
        default_factory=make_topic_segment_id,
        min_length=1,
        description="系统内部稳定唯一标识",
    )

    stream_id: str = Field(
        min_length=1,
        description="关联所属 Stream 的稳定唯一标识",
    )

    source_part_ids: list[str] = Field(
        min_length=1,
        description="当前话题范围涉及的 StreamPart ID 列表",
    )

    reaction_match_ids: list[str] = Field(
        min_length=1,
        description="支撑当前话题形成的一组 ReactionMatch ID",
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
        description="对当前话题内容的简短概括",
    )

    summary: str = Field(
        min_length=1,
        description="对当前话题主要内容的简要总结",
    )

    keywords: list[str] = Field(
        description="用于检索和话题识别的关键词",
    )

    entities: list[str] = Field(
        description="当前话题涉及的人物、作品、地点等实体",
    )

    transcript_segment_ids: list[str] = Field(
        min_length=1,
        description="用于判断话题内容和语义边界的转写证据 ID 列表",
    )

    salience_score: float = Field(
        ge=0.0,
        le=1.0,
        description="根据相关 Highlight 等信号计算的话题显著程度，范围 [0,1]",
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="系统对当前话题划分及语义分析结果的可信程度，范围 [0,1]",
    )

    analyzer_version: str = Field(
        min_length=1,
        description="生成当前 TopicSegment 时使用的话题分析算法或模型版本",
    )
    
    topic_type: TopicType = Field(
        description="当前话题的一级内容分类",
    )

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.end_ms <= self.start_ms:
            raise ValueError(
                "end_ms must be greater than start_ms"
            )

        return self