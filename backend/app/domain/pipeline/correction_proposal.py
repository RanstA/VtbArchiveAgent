import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def make_correction_proposal_id() -> str:
    return str(uuid.uuid4())


class CorrectionProposal(BaseModel):
    """Auditable suggestion; creating it never changes the target archive."""

    id: str = Field(default_factory=make_correction_proposal_id, min_length=1)
    stream_id: str = Field(min_length=1)
    target_type: Literal["topic_segment", "stream"]
    target_id: str = Field(min_length=1)
    supplemental_evidence_ids: list[str] = Field(min_length=1)
    proposal: str
    reason: str
    status: Literal["pending", "accepted", "rejected"] = "pending"
    created_at: datetime
    reviewed_at: datetime | None = None
    review_note: str | None = None

    @field_validator("supplemental_evidence_ids")
    @classmethod
    def validate_unique_evidence_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("duplicate supplemental_evidence_ids")
        return value
