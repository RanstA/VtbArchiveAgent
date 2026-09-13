import uuid
from typing import Self

from pydantic import BaseModel, Field, model_validator


def make_highlight_id(
    stream_id: str,
    part_id: str,
    start_ms: int,
    end_ms: int,
) -> str:
    """
    根据高光所属直播、Part 和时间范围生成稳定 UUID。

    同一个：

        stream_id
        + part_id
        + start_ms
        + end_ms

    无论 detector 重跑多少次，
    都会生成相同的 Highlight ID。

    detector score、peak_ms 等检测细节
    不参与 ID 生成。
    """

    key = (
        f"{stream_id}|"
        f"{part_id}|"
        f"{start_ms}|"
        f"{end_ms}"
    )

    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            key,
        )
    )


class Highlight(BaseModel):
    """
    一个约 30 秒、值得用户点进去回看的直播高光候选。

    Highlight 保存 detector 的检测结果。

    Top texts、附近弹幕等 Evidence
    不在这里保存，而是在查询时根据
    part_id + 时间范围动态获取。
    """

    # Highlight 的稳定唯一 ID。
    id: str

    # 所属直播。
    stream_id: str

    # 所属直播 Part。
    #
    # 当前时间字段均为 Part 内局部时间。
    part_id: str

    # 建议回看的时间范围。
    start_ms: int = Field(
        ge=0
    )

    end_ms: int = Field(
        gt=0
    )

    # 当前 30 秒 Highlight 内部
    # 观众反应最强的时间锚点。
    #
    # 注意：
    # 它不是主播内容精确发生时间。
    peak_ms: int = Field(
        ge=0
    )

    # Detector 最终综合得分。
    score: float = Field(
        ge=0.0,
        le=1.0,
    )

    # Detector 的三个归一化信号得分。
    density_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    repetition_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    reaction_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    # 当前窗口中的原始统计信息。
    #
    # 这些信息用于解释：
    # “为什么 detector 认为这里值得看？”
    danmaku_count: int = Field(
        ge=0
    )

    unique_text_count: int = Field(
        ge=0
    )

    repetition_ratio: float = Field(
        ge=0.0,
        le=1.0,
    )

    reaction_ratio: float = Field(
        ge=0.0,
        le=1.0,
    )

    laugh_count: int = Field(
        ge=0
    )

    question_count: int = Field(
        ge=0
    )

    exclamation_count: int = Field(
        ge=0
    )

    # 记录产生该 Highlight 的 detector 版本。
    #
    # V0.1：
    #
    # 30s window
    # 10s stride
    # density / repetition / reaction
    detector_version: str = Field(
        min_length=1
    )

    @model_validator(
        mode="after"
    )
    def validate_time_range(
        self,
    ) -> Self:
        """
        保证 Highlight 的时间范围合法。
        """

        if self.end_ms <= self.start_ms:
            raise ValueError(
                "end_ms must be greater than start_ms"
            )

        if not (
            self.start_ms
            <= self.peak_ms
            < self.end_ms
        ):
            raise ValueError(
                "peak_ms must be inside "
                "[start_ms, end_ms)"
            )

        return self