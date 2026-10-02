from dataclasses import (
    dataclass,
    field,
)
from typing import (
    Any,
    Protocol,
)

from app.domain.source.vtuber import Vtuber
from app.domain.source.stream import (
    Stream,
)
from app.domain.source.stream_part import (
    StreamPart,
)



@dataclass(slots=True)
class ArchiveBundle:
    """
    不同 Archive Source 的统一输出。
    Stream / StreamPart / 尚未持久化的弹幕字段。
    """
    source: str
    vtuber: Vtuber
    
    stream: Stream
    parts: list[StreamPart]
    danmaku: list[dict[str, str | int]]
    
    source_metadata: dict[str, Any] = field(
        default_factory=dict
    )
    
class ArchiveSource(Protocol):

    def load(self) -> ArchiveBundle:
        ...
        
