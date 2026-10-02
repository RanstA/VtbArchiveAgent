import uuid

from pydantic import BaseModel, Field, model_validator


def make_transcript_segment_id() -> str:
    """
    生成系统内部稳定的 TranscriptSegment ID。
    创建后应持久化保存，不重新生成。
    """
    return str(uuid.uuid4())


class TranscriptSegment(BaseModel):
    """
    TranscriptSegment 表示某个 StreamPart 中一段带时间范围的主播语音转写结果，
    属于 Speech Evidence。

    start_ms 与 end_ms 均使用当前直播分段内的局部时间。
    """

    id: str = Field(
        default_factory=make_transcript_segment_id,
        min_length=1,
        description="系统内部稳定唯一标识，用于 Evidence 引用",
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
        description="当前转写片段在直播分段内的开始时间，单位毫秒",
    )

    end_ms: int = Field(
        ge=0,
        description="当前转写片段在直播分段内的结束时间，单位毫秒",
    )

    raw_text: str = Field(
        description="从字幕或 ASR 来源中读取到的原始转写文本，用于追溯",
    )

    text: str = Field(
        description="经过基础清洗后的文本，用于检索、对齐和语义分析",
    )

    source: str = Field(
        min_length=1,
        description="转写结果来源，例如 bilibili_ai、local_asr、online_asr",
    )

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")

        return self
