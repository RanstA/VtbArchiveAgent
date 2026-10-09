"""Query-time DeepResearch DTOs; no new persisted archive entities."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class DeepResearchError(RuntimeError):
    pass


class CitationGuardError(DeepResearchError):
    pass


class StructuredOutputError(DeepResearchError):
    """Safe diagnostics only: never retain model content or validation inputs."""

    def __init__(self, stage: str, error_type: str, *, attempt: int, fields: tuple[str, ...] = ()):
        self.stage = stage
        self.error_type = error_type
        self.attempt = attempt
        self.fields = fields
        super().__init__(
            f"{stage}: invalid structured JSON ({error_type}; attempts={attempt})"
        )


class ResearchModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True,
        extra="forbid", strict=True, str_strip_whitespace=True,
    )


SearchTerm = Annotated[str, Field(min_length=1, max_length=24)]
EvidenceKind = Literal["speech", "audience_reaction", "archived_interpretation"]


class QueryPlan(ResearchModel):
    terms: list[SearchTerm] = Field(min_length=1, max_length=3)


class EvidenceLocation(ResearchModel):
    evidence_ref: str
    stream_id: str
    source_part_ids: list[str]
    # A TopicSegment has a global range and potentially multiple Parts, not one
    # authoritative Part-local range. Null is intentional for topic references.
    part_id: str | None
    local_start_ms: int | None
    local_end_ms: int | None
    stream_start_ms: int
    stream_end_ms: int | None


class ResearchEvidence(ResearchModel):
    evidence_id: str
    kind: EvidenceKind
    text: str
    source: str | None
    location: EvidenceLocation
    is_seed: bool = False
    text_truncated: bool = False


class EvidenceQuotation(ResearchModel):
    evidence_ref: str = Field(min_length=1, max_length=200)
    quote: str = Field(min_length=1, max_length=1_000)


class FindingDraft(ResearchModel):
    kind: EvidenceKind
    citations: list[EvidenceQuotation] = Field(min_length=1, max_length=8)


class ResearchDraft(ResearchModel):
    # The model chooses supported excerpts; it cannot inject an unguarded answer.
    findings: list[FindingDraft] = Field(max_length=8)
    insufficient_evidence: bool
    limitations: list[Literal["insufficient_context", "ambiguous_reference"]] = Field(
        default_factory=list, max_length=2,
    )


class ResearchFinding(ResearchModel):
    kind: EvidenceKind
    statement: str
    evidence_refs: list[str]
    citations: list[EvidenceQuotation]


class ResearchReport(ResearchModel):
    query: str
    vtuber_id: str
    search_terms: list[str]
    answer: str
    findings: list[ResearchFinding]
    evidence_refs: list[str]
    locations: list[EvidenceLocation]
    limitations: list[str]
