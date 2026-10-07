from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.domain.evidence import SupplementalEvidence
from app.domain.pipeline import CorrectionProposal
from app.product import SearchHit


CREATED_AT = datetime(2026, 10, 8, 12, 30, tzinfo=timezone.utc)


def test_supplemental_evidence_model_generates_uuid() -> None:
    evidence = SupplementalEvidence(
        stream_id="stream-1",
        topic_segment_id=None,
        source_type="user_text",
        content="补充背景",
        source_url=None,
        created_at=CREATED_AT,
    )
    assert UUID(evidence.id).version == 4
    assert evidence.stream_id == "stream-1"
    assert evidence.created_at == CREATED_AT


@pytest.mark.parametrize(
    "changes",
    [{"source_type": "unknown"}, {"content": ""}],
)
def test_supplemental_evidence_rejects_invalid_input(changes: dict) -> None:
    values = {
        "stream_id": "stream-1",
        "source_type": "user_text",
        "content": "补充背景",
        "created_at": CREATED_AT,
    }
    with pytest.raises(ValidationError):
        SupplementalEvidence(**(values | changes))


def test_correction_proposal_model_defaults_to_pending() -> None:
    proposal = CorrectionProposal(
        stream_id="stream-1",
        target_type="stream",
        target_id="stream-1",
        supplemental_evidence_ids=["evidence-1"],
        proposal="建议修正标题",
        reason="补充资料显示旧标题有误",
        created_at=CREATED_AT,
    )
    assert UUID(proposal.id).version == 4
    assert proposal.status == "pending"
    assert proposal.reviewed_at is None

    reviewed = proposal.model_copy(
        update={"status": "accepted", "reviewed_at": CREATED_AT, "review_note": "已核实"}
    )
    restored = CorrectionProposal.model_validate_json(reviewed.model_dump_json())
    assert restored.reviewed_at == CREATED_AT
    assert restored.review_note == "已核实"


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "auto_accepted"},
        {"target_type": "highlight"},
        {"supplemental_evidence_ids": ["same", "same"]},
        {"supplemental_evidence_ids": []},
        {"proposal": ""},
        {"reason": ""},
    ],
)
def test_correction_proposal_rejects_invalid_input(changes: dict) -> None:
    values = {
        "stream_id": "stream-1",
        "target_type": "stream",
        "target_id": "stream-1",
        "supplemental_evidence_ids": ["evidence-1"],
        "proposal": "建议修正标题",
        "reason": "补充资料",
        "created_at": CREATED_AT,
    }
    with pytest.raises(ValidationError):
        CorrectionProposal(**(values | changes))


def test_search_hit_is_a_query_time_dto() -> None:
    hit = SearchHit(
        stream_id="stream-1",
        topic_segment_id="topic-1",
        start_ms=1_000,
        end_ms=2_000,
        title="某段话题",
        snippet="匹配查询的摘要",
        score=0.82,
        evidence_ids=["transcript:segment-1"],
    )
    assert hit.evidence_ids == ["transcript:segment-1"]
    assert SearchHit.model_validate(hit.model_dump()) == hit


@pytest.mark.parametrize("changes", [{"title": ""}, {"snippet": ""}])
def test_search_hit_rejects_empty_text(changes: dict) -> None:
    values = {
        "stream_id": "stream-1",
        "title": "标题",
        "snippet": "摘要",
        "score": 0.5,
    }
    with pytest.raises(ValidationError):
        SearchHit(**(values | changes))


@pytest.mark.parametrize(
    "start_ms,end_ms",
    [(-1, 10), (0, -1), (10, 10), (20, 10)],
)
def test_search_hit_rejects_invalid_time_range(
    start_ms: int, end_ms: int,
) -> None:
    with pytest.raises(ValidationError):
        SearchHit(
            stream_id="stream-1",
            start_ms=start_ms,
            end_ms=end_ms,
            title="标题",
            snippet="摘要",
            score=1.0,
        )


def test_search_hit_allows_unlocated_result() -> None:
    hit = SearchHit(stream_id="stream-1", title="标题", snippet="摘要", score=0.5)
    assert hit.topic_segment_id is None
    assert hit.start_ms is None and hit.end_ms is None
    assert hit.evidence_ids is None
