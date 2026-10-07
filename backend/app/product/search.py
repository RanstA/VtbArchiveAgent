from pydantic import BaseModel, Field, model_validator


class SearchHit(BaseModel):
    """Query-time result projection, not a persisted archive entity."""

    stream_id: str = Field(min_length=1)
    topic_segment_id: str | None = None
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    title: str
    snippet: str
    score: float
    evidence_ids: list[str] | None = None

    @model_validator(mode="after")
    def validate_time_range(self):
        if (
            self.start_ms is not None
            and self.end_ms is not None
            and self.end_ms <= self.start_ms
        ):
            raise ValueError("end_ms must be greater than start_ms")
        return self
