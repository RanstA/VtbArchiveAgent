from pydantic import BaseModel, Field


class StreamPart(BaseModel):
    """
    StreamPart 表示一场 Stream 中的单个录播分段。

    同一个直播分段可以同时具有 Bilibili 平台定位信息和本地档案。
    当对应 Bilibili 资源仍可访问时，优先使用在线资源；
    本地档案作为补充或离线来源。
    """

    stream_id: str = Field(min_length=1, description="关联所属 Stream 的稳定唯一标识")

    part_id: str = Field(
        min_length=1,
        description="所属 Stream 内的录播分段标识，与 stream_id 共同定位一个直播分段",
    )

    start_offset_ms: int = Field(
        default=0,
        ge=0,
        description="当前 Part 在整场 Stream 时间轴上的起始位置，单位毫秒",
    )

    bvid: str | None = Field(
        default=None,
        min_length=1,
        description="当前 Part 所属的 Bilibili 视频 BV 号",
    )

    cid: str | None = Field(
        default=None,
        min_length=1,
        description="当前 Part 在 Bilibili 中对应的 CID，用于定位具体分 P 及字幕等平台资源",
    )

    page: int | None = Field(
        default=None,
        ge=1,
        description="当前 Part 在对应 BV 中的分 P 序号",
    )

    duration_ms: int | None = Field(
        default=None,
        gt=0,
        description="当前 Part 的实际媒体时长，单位毫秒",
    )

    video_path: str | None = Field(
        default=None,
        description="当前 Part 对应的本地视频文件路径",
    )

    danmaku_path: str | None = Field(
        default=None,
        description="当前 Part 对应的 ASS 弹幕文件路径",
    )

    xml_path: str | None = Field(
        default=None,
        description="当前 Part 对应的原始 XML 弹幕文件路径",
    )
