from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])

class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class EvidenceRef(ApiModel):
    kind: Literal["highlight", "danmaku"]
    id: str

class EventScoutTraceStep(ApiModel):
    step: int
    action: Literal["model", "tool", "final"]
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None

class EventScoutFinding(ApiModel):
    highlight_id: str
    stream_id: str
    stream_title: str
    live_time: str
    part_id: str
    start_ms: int
    end_ms: int
    peak_ms: int
    score: float
    observation: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_level: Literal["audience_reaction"] = "audience_reaction"
    evidence: list[EvidenceRef]

class EventScoutResult(ApiModel):
    query: str
    vtuber_id: str
    scout: Literal["event_scout"] = "event_scout"
    boundary: Literal["audience_reaction_only"] = "audience_reaction_only"
    answer: str
    findings: list[EventScoutFinding]
    trace: list[EventScoutTraceStep]

class EventScoutDraftFinding(BaseModel):
    highlight_id: str
    observation: str
    interpretation: str | None = None
    confidence: float
    danmaku_ids: list[int] = Field(default_factory=list)

class EventScoutDraft(BaseModel):
    answer: str
    findings: list[EventScoutDraftFinding]