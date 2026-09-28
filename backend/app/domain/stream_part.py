from pydantic import BaseModel, Field


class StreamPart(BaseModel):
    stream_id: str
    part_id: str
    
    start_offset_ms: int = Field(
        default=0,
        ge=0
    )
    
    duration_ms: int | None = Field(
        default=None,
        gt=0,
    )

    video_path: str | None = None
    danmaku_path: str | None = None
    xml_path: str | None = None
