import uuid

from pydantic import BaseModel, Field, model_validator


def make_highlight_id() -> str:
    """
    生成系统内部稳定的 Highlight ID。

    Highlight 创建后应持久化保存，
    后续引用使用该 ID，不重新生成。
    """
    return str(uuid.uuid4())


class Highlight(BaseModel):
    """
    Highlight 表示由离线 Highlight Detector
    根据弹幕统计信号发现的高观众反应候选区域。

    start_ms、end_ms 与 peak_ms
    均使用当前 StreamPart 内的局部时间。
    """

    id: str = Field(
        default_factory=make_highlight_id,
        min_length=1,
        description="Highlight 的稳定唯一标识",
    )

    stream_id: str = Field(
        min_length=1,
        description="关联所属 Stream 的稳定唯一标识",
    )

    part_id: str = Field(
        min_length=1,
        description="关联所属 StreamPart，与 stream_id 共同定位直播分段",
    )

    start_ms: int = Field(
        ge=0,
        description="当前 Highlight 候选区域的起始时间，基于 Part 内局部时间，单位毫秒",
    )

    end_ms: int = Field(
        ge=0,
        description="当前 Highlight 候选区域的结束时间，基于 Part 内局部时间，单位毫秒",
    )

    peak_ms: int = Field(
        ge=0,
        description="当前 Highlight 中观众反应最强的时间锚点，不代表主播行为发生的精确时间",
    )

    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Highlight Detector 的综合评分，范围 [0,1]",
    )

    density_score: float = Field(
        ge=0.0,
        le=1.0,
        description="当前时间段弹幕密度信号得分，范围 [0,1]",
    )

    repetition_score: float = Field(
        ge=0.0,
        le=1.0,
        description="当前时间段弹幕文本重复信号得分，范围 [0,1]",
    )

    reaction_score: float = Field(
        ge=0.0,
        le=1.0,
        description="当前时间段观众反应信号得分，范围 [0,1]",
    )

    reaction_ratio: float = Field(
        ge=0.0,
        le=1.0,
        description="当前窗口内反应类弹幕所占比例，范围 [0,1]",
    )

    danmaku_count: int = Field(
        ge=0,
        description="当前 Highlight 时间范围内的弹幕总数",
    )

    unique_text_count: int = Field(
        ge=0,
        description="当前 Highlight 中去重后的弹幕文本数量",
    )

    repetition_ratio: float = Field(
        ge=0.0,
        le=1.0,
        description="当前窗口内重复弹幕所占比例，范围 [0,1]",
    )

    laugh_count: int = Field(
        ge=0,
        description="笑声类弹幕数量",
    )

    question_count: int = Field(
        ge=0,
        description="疑问类弹幕数量",
    )

    exclamation_count: int = Field(
        ge=0,
        description="感叹类弹幕数量",
    )

    detector_version: str = Field(
        min_length=1,
        description="生成该 Highlight 时使用的 Detector 版本",
    )

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")

        if not (self.start_ms <= self.peak_ms < self.end_ms):
            raise ValueError("peak_ms must be within " "[start_ms, end_ms)")

        return self
