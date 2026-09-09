from datetime import datetime

from pydantic import BaseModel


class Stream(BaseModel):
    id: str
    month: str
    live_time: datetime
    publish_times: list[datetime]

    bv_id: str
    title: str
    video_url: str
    status: str
    
    archive_dir: str | None = None
    
