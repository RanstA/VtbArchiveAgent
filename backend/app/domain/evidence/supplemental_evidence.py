import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


def make_supplemental_evidence_id() -> str:
    return str(uuid.uuid4())


class SupplementalEvidence(BaseModel):
    """Received supplemental material, not a verified archive fact."""

    id: str = Field(default_factory=make_supplemental_evidence_id, min_length=1)
    stream_id: str = Field(min_length=1)
    topic_segment_id: str | None = None
    source_type: Literal["user_text", "fan_summary", "external_link"]
    content: str = Field(min_length=1)
    source_url: str | None = None
    created_at: datetime
