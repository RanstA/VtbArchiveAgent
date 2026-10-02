import uuid

from pydantic import BaseModel, Field


def make_reaction_match_id() -> str:
    """
    生成系统内部稳定的 ReactionMatch ID。
    创建后应持久化保存，不重新生成。
    """
    return str(uuid.uuid4())


class ReactionMatch(BaseModel):
    """
    ReactionMatch 表示系统根据 Highlight、弹幕和转写证据，
    对主播发言与观众反应建立的一次基础关联结果。

    ReactionMatch 不负责判断完整话题语义。
    """

    id: str = Field(
        default_factory=make_reaction_match_id,
        min_length=1,
        description="系统内部稳定唯一标识",
    )

    stream_id: str = Field(
        min_length=1,
        description="关联所属 Stream 的稳定唯一标识",
    )

    part_id: str = Field(
        min_length=1,
        description="关联所属 StreamPart，与 stream_id 共同定位直播分段",
    )

    highlight_id: str = Field(
        min_length=1,
        description="当前关联结果对应的 Highlight",
    )

    transcript_segment_ids: list[str] = Field(
        min_length=1,
        description="被判断为与当前观众反应相关的主播发言片段 ID 列表",
    )

    danmaku_ids: list[int] = Field(
        min_length=1,
        description="用于建立当前关联关系的代表性弹幕证据 ID 列表",
    )

    matcher_version: str = Field(
        min_length=1,
        description="生成当前关联结果时使用的反应匹配算法版本",
    )