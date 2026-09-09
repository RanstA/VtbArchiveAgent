from pydantic import BaseModel


class StreamPart(BaseModel):
    stream_id: str
    part_id: str

    video_path: str | None = None
    danmaku_path: str | None = None
    xml_path: str | None = None
