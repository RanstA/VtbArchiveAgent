import uuid
from typing import Self

from pydantic import BaseModel, Field, model_validator


def make_event_id(
    stream_id: str,
    part_id: str,
    source_highlight_ids: list[str],
) -> str:
    """
    根据 Event 所属 Stream、Part
    和组成它的 Highlight 集合生成稳定 UUID。

    Semanticizer 的输出不参与 ID，
    因此重新生成 title / summary 等语义信息
    不会改变 Event 身份。
    """

    if not source_highlight_ids:
        raise ValueError(
            "source_highlight_ids must not be empty"
        )

    highlight_key = "|".join(
        sorted(source_highlight_ids)
    )

    key = (
        f"{stream_id}|"
        f"{part_id}|"
        f"{highlight_key}"
    )

    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            key,
        )
    )


class Event(BaseModel):
    """
    从一个或多个相邻 Highlight Candidate
    合并并语义化得到的可检索直播事件。

    Event 是后续 BM25 / Vector / RRF
    的核心检索单元。

    当前时间字段均为 Part 内局部时间。
    """

    # 稳定唯一 ID。
    id: str

    # 所属直播。
    stream_id: str

    # 当前 V1 Event 不跨 Part。
    part_id: str

    # Event 覆盖范围。
    start_ms: int = Field(
        ge=0
    )

    end_ms: int = Field(
        gt=0
    )

    # Event 中最值得跳转查看的时间锚点。
    peak_ms: int = Field(
        ge=0
    )

    # 组成该 Event 的 Highlight IDs。
    source_highlight_ids: list[str] = Field(
        min_length=1
    )

    # Semanticizer 生成的简短事件标题。
    title: str = Field(
        min_length=1
    )

    # 对当前 Event 的证据约束语义总结。
    summary: str = Field(
        min_length=1
    )

    # 适合词法检索的主题词。
    keywords: list[str] = Field(
        default_factory=list
    )

    # 人物、作品、游戏、梗等实体。
    entities: list[str] = Field(
        default_factory=list
    )

    # BM25 与 Vector Retrieval
    # 使用的统一语义检索文本。
    semantic_text: str = Field(
        min_length=1
    )

    # 记录生成语义信息的 Semanticizer 版本。
    semanticizer_version: str = Field(
        min_length=1
    )

    @model_validator(
        mode="after"
    )
    def validate_event(
        self,
    ) -> Self:
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

        if (
            len(self.source_highlight_ids)
            != len(set(self.source_highlight_ids))
        ):
            raise ValueError(
                "source_highlight_ids "
                "must be unique"
            )

        return self