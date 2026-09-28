import uuid
from typing import Self

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)


def make_event_id(
    stream_id: str,
    start_ms: int,
    end_ms: int,
) -> str:
    """
    根据 Event 所属 Stream 和
    Stream-global 时间边界生成稳定 UUID。

    Event 的 source Part、Highlight、
    Semanticizer 输出均不参与 ID。

    因此只要事件时间边界不变，
    重新语义化不会改变 Event 身份。
    """

    if start_ms < 0:
        raise ValueError("start_ms must be >= 0")

    if end_ms <= start_ms:
        raise ValueError("end_ms must be greater than start_ms")

    key = f"{stream_id}|" f"{start_ms}|" f"{end_ms}"

    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            key,
        )
    )


class Event(BaseModel):
    """
    直播中一段具有相对完整语义的
    话题或事件片段。

    Event 的语义边界独立于 StreamPart
    的技术文件切分，因此允许跨 Part。

    所有时间字段统一使用
    Stream-global 时间。
    """

    # 稳定唯一 ID。
    id: str

    # 所属直播。
    stream_id: str

    # Event 覆盖或引用到的 Stream Parts。
    # 一个 Event 可以跨多个 Part。
    source_part_ids: list[str] = Field(min_length=1)

    # Event 在整场 Stream 时间轴上的范围。
    start_ms: int = Field(ge=0)

    end_ms: int = Field(gt=0)

    # 整场 Stream 时间轴上的推荐跳转位置。
    anchor_ms: int = Field(ge=0)

    # 与当前 Event 关联的 Highlight IDs。
    # 普通 Timeline Event 可以为空。
    source_highlight_ids: list[str] = Field(default_factory=list)

    # Semanticizer 生成的简短事件标题。
    title: str = Field(min_length=1)

    # 在 Evidence Boundary 下生成的事件摘要。
    summary: str = Field(min_length=1)

    # 用于词法检索和主题表达的关键词。
    keywords: list[str] = Field(default_factory=list)

    # 人物、作品、游戏、梗等实体。
    entities: list[str] = Field(default_factory=list)

    # BM25 / Vector Retrieval
    # 使用的统一语义检索文本。
    semantic_text: str = Field(min_length=1)

    # Event 作为名场面 / 高光展示的显著程度。
    salience_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    # 生成当前时间边界的 Segmenter 版本。
    segmenter_version: str = Field(min_length=1)

    # 生成当前语义字段的 Semanticizer 版本。
    semanticizer_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_event(
        self,
    ) -> Self:
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")

        if not (self.start_ms <= self.anchor_ms < self.end_ms):
            raise ValueError("anchor_ms must be inside " "[start_ms, end_ms)")

        if len(self.source_part_ids) != len(set(self.source_part_ids)):
            raise ValueError("source_part_ids must be unique")

        if len(self.source_highlight_ids) != len(set(self.source_highlight_ids)):
            raise ValueError("source_highlight_ids must be unique")

        return self
