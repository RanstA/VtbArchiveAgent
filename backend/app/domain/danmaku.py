from pydantic import BaseModel


class Danmaku(BaseModel):
    stream_id: str
    part_id: str
    timestamp_ms: int

    raw_text: str   # ASS 原始文本，保留用于追溯
    text: str       # 去除 ASS 样式后的正文