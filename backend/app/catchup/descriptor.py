from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
)


class ImportantMomentDescriptor(BaseModel):
    """
    一场直播中值得交给 Catch-up
    后续阶段继续处理的重要时间点。

    anchor_ms:
    Stream-global 时间。

    local_anchor_ms:
    Part-local 时间，
    可用于回放精准空降。
    """

    anchor_ms: int = Field(ge=0)

    local_anchor_ms: int = Field(ge=0)

    source_part_ids: list[str] = Field(
        min_length=1,
    )

    salience_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    source_highlight_ids: list[str] = Field(
        default_factory=list,
    )


class StreamDescriptor(BaseModel):
    """
    一场直播的压缩表示。

    这是后续 Catch-up / 回坑补课
    输入层的数据结构，
    不包含 LLM 生成内容。
    """

    stream_id: str

    title: str

    live_time: datetime

    duration_ms: int | None = Field(
        default=None,
        gt=0,
    )

    bv_ids: list[str] = Field(
        default_factory=list,
    )

    important_moments: list[ImportantMomentDescriptor] = Field(
        default_factory=list,
    )
