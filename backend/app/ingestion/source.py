from dataclasses import (
    dataclass,
    field,
)
from typing import (
    Any,
    Protocol,
)

from app.domain.vtuber import (
    Vtuber,
    VtuberSources,
)
from app.domain.danmaku import (
    Danmaku,
)
from app.domain.stream import (
    Stream,
)
from app.domain.stream_part import (
    StreamPart,
)



@dataclass(slots=True)
class ArchiveBundle:
    """
    不同 Archive Source 的统一输出。
    Stream / StreamPart / Danmaku。
    """
    source: str
    vtuber: Vtuber
    vtuber_sources: list[VtuberSources]
    
    stream: Stream
    parts: list[StreamPart]
    danmaku: list[Danmaku]
    
    source_metadata: dict[str, Any] = field(
        default_factory=dict
    )
    
class ArchiveSource(Protocol):

    def load(self) -> ArchiveBundle:
        ...
        
