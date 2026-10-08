"""Deterministic DeepResearch tests: isolated SQLite, no network/model service."""

import json

import httpx
import pytest

import app.investigation.deep_research as research
from app.investigation.deep_research import DeepResearchAgent
from app.investigation.deep_research_models import CitationGuardError, DeepResearchError
from app.investigation.model_client import ModelClientError, OpenAICompatibleChatClient
from search_fixtures import search_db, seed_topic
from test_investigation_evidence import db, add_danmaku, add_transcript


QUESTION = "主播最近有没有提到车祸？"


class FakeModelClient:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, *, messages, tools=None):
        assert tools is None
        self.calls.append(messages)
        assert self.replies, "unexpected extra model call"
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            reply = reply(json.loads(messages[-1]["content"]))
        return {"content": reply if isinstance(reply, str) else json.dumps(reply, ensure_ascii=False)}


def draft(kind="speech", ref="transcript:seed", quote="车祸"):
    return {
        "findings": [{"kind": kind, "citations": [{"evidenceRef": ref, "quote": quote}]}],
        "insufficientEvidence": False,
    }


def extract_all(payload):
    return {
        "findings": [
            {"kind": item["kind"],
             "citations": [{"evidenceRef": item["evidenceId"], "quote": item["text"]}]}
            for item in payload["evidence"][:8]
        ],
        "insufficientEvidence": False,
    }


def run(db, reply=extract_all, **options):
    model = FakeModelClient({"terms": ["车祸"]}, reply)
    report = DeepResearchAgent(model=model, **options).run(db, query=QUESTION, vtuber_id="v1")
    return report, model


def test_natural_language_planning():
    model = FakeModelClient({"terms": ["车祸", "演唱", "观众"]})
    plan = DeepResearchAgent(model=model).plan_query("车祸和演唱时观众有什么反应？")
    assert plan.terms == ["车祸", "演唱", "观众"]
    assert len(model.calls) == 1


@pytest.mark.parametrize("response", [
    {"terms": []}, {"terms": [" "]}, {"terms": [1]},
    {"terms": ["车祸", "车祸"]},
    {"terms": ["车祸", "主播", "最近", "提到"]},
    {"terms": [QUESTION]}, {"terms": [QUESTION.rstrip("？")]},
    {"terms": ["不存在的同义词"]},
    {"terms": ["车祸"], "extra": True},
    '{"terms":["车祸"],"terms":["主播"]}',
    '{"terms": NaN}', chr(96) * 3 + 'json\n{"terms":["车祸"]}', 'not JSON',
])
def test_planner_rejects_invalid_or_sentence_queries(response):
    with pytest.raises(DeepResearchError, match="planner:"):
        DeepResearchAgent(model=FakeModelClient(response)).plan_query(QUESTION)


def test_fake_end_to_end_speech_only(db):
    add_transcript(db, 10_000, 12_000, "刚才提到车祸这个词", part_id="p1", id="seed")
    db.commit()
    before = list(db.iterdump())
    report, model = run(db, draft(quote="刚才提到车祸这个词"))
    assert report.evidence_refs == ["transcript:seed"]
    location = report.locations[0]
    assert (location.stream_id, location.part_id) == ("s1", "p1")
    assert (location.local_start_ms, location.local_end_ms) == (10_000, 12_000)
    assert (location.stream_start_ms, location.stream_end_ms) == (110_000, 112_000)
    assert report.findings[0].kind == "speech"
    assert "字幕转写记载" in report.answer
    evidence = json.loads(model.calls[1][-1]["content"])["evidence"]
    assert evidence[0]["source"] == "test_subtitle"
    assert list(db.iterdump()) == before
    assert not db.in_transaction
    assert len(model.calls) == 2
    print(json.dumps(report.model_dump(by_alias=True), ensure_ascii=False, indent=2))


def test_audience_only_cannot_become_streamer_facts(db):
    row_id = add_danmaku(db, 12_000, "车祸了？", part_id="p1")
    report, model = run(db, draft("audience_reaction", f"danmaku:{row_id}", "车祸了？"))
    assert report.findings[0].kind == "audience_reaction"
    assert "观众弹幕中出现" in report.answer
    assert any("不能据此确认主播" in note for note in report.limitations)
    assert report.locations[0].stream_start_ms == 112_000
    assert report.locations[0].local_start_ms == 12_000
    assert report.locations[0].local_end_ms is None
    assert all(item["kind"] == "audience_reaction"
               for item in json.loads(model.calls[1][-1]["content"])["evidence"])


def test_cross_stream_and_part_locations_with_vtuber_isolation(db):
    for stream, part in (("s1", "p0"), ("s1", "p1"), ("s2", "p0"), ("s3", "p0")):
        add_transcript(db, 10_000, 11_000, "车祸", stream_id=stream, part_id=part,
                       id=f"{stream}-{part}")
    report, _ = run(db)
    assert {(loc.stream_id, loc.part_id) for loc in report.locations} == {
        ("s1", "p0"), ("s1", "p1"), ("s2", "p0"),
    }
    for loc in report.locations:
        assert loc.stream_start_ms == (110_000 if loc.part_id == "p1" else 10_000)


def test_topic_is_existing_interpretation_not_speech(search_db):
    seed_topic(search_db, title="车祸相关话题", parts=("p0", "p1"))
    model = FakeModelClient({"terms": ["车祸"]}, extract_all)
    report = DeepResearchAgent(model=model).run(search_db, query=QUESTION, vtuber_id="aza")
    assert report.evidence_refs == ["topic:topic-1"]
    assert report.findings[0].kind == "archived_interpretation"
    assert "已有话题档案的解释" in report.answer
    assert any("不等同于" in note for note in report.limitations)
    loc = report.locations[0]
    assert loc.source_part_ids == ["p0", "p1"]
    assert loc.part_id is loc.local_start_ms is loc.local_end_ms is None
    assert loc.stream_start_ms == 101_000


def test_no_evidence_skips_report_model(db):
    model = FakeModelClient({"terms": ["车祸"]})
    report = DeepResearchAgent(model=model).run(db, query=QUESTION, vtuber_id="v1")
    assert report.findings == report.evidence_refs == report.locations == []
    assert "证据不足" in report.answer
    assert len(model.calls) == 1


@pytest.mark.parametrize("ref", ["transcript:invented", "danmaku:999", "topic:invented",
                                 "transcript:outside"])
def test_guard_rejects_fabricated_and_unretrieved_citations(db, ref):
    add_transcript(db, 10_000, 11_000, "车祸", id="seed")
    add_transcript(db, 90_000, 91_000, "没有命中", id="outside")
    with pytest.raises(CitationGuardError, match="unretrieved citation"):
        run(db, draft(ref=ref))


def test_guard_rejects_audience_as_speech(db):
    row_id = add_danmaku(db, 10_000, "车祸")
    with pytest.raises(CitationGuardError, match="source cannot support"):
        run(db, draft("speech", f"danmaku:{row_id}"))


def test_guard_rejects_topic_as_speech(search_db):
    seed_topic(search_db, title="车祸")
    model = FakeModelClient({"terms": ["车祸"]}, draft("speech", "topic:topic-1"))
    with pytest.raises(CitationGuardError, match="source cannot support"):
        DeepResearchAgent(model=model).run(search_db, query=QUESTION, vtuber_id="aza")


def test_guard_rejects_invented_quote_even_with_valid_id(db):
    add_transcript(db, 10_000, 11_000, "车祸", id="seed")
    with pytest.raises(CitationGuardError, match="quotation is not"):
        run(db, draft(quote="主播承认发生了真实交通事故"))


@pytest.mark.parametrize("extra", ["answer", "locations", "statement"])
def test_model_cannot_bypass_guard_with_unvalidated_text(db, extra):
    add_transcript(db, 10_000, 11_000, "车祸", id="seed")
    response = draft()
    response[extra] = "任意未经引用校验的结论"
    with pytest.raises(DeepResearchError, match="report: invalid structured JSON"):
        run(db, response)


@pytest.mark.parametrize("stage", ["planner", "report"])
@pytest.mark.parametrize("failure, label", [
    (ModelClientError("offline"), "model call failed"),
    (TimeoutError("late"), "model timeout"),
    (httpx.ReadTimeout("late"), "model timeout"),
    ('{"broken"', "invalid structured JSON"),
])
def test_model_failures_are_explicit(db, stage, failure, label):
    add_transcript(db, 10_000, 11_000, "车祸", id="seed")
    replies = [failure] if stage == "planner" else [{"terms": ["车祸"]}, failure]
    with pytest.raises(DeepResearchError, match=f"{stage}: {label}"):
        DeepResearchAgent(model=FakeModelClient(*replies)).run(
            db, query=QUESTION, vtuber_id="v1",
        )


def test_reuses_real_client_and_timeout_is_preserved(db, monkeypatch):
    def fail(*args, **kwargs):
        assert kwargs["timeout"] == 0.5
        raise httpx.ReadTimeout("test timeout")
    monkeypatch.setattr(httpx, "post", fail)
    client = OpenAICompatibleChatClient(base_url="https://unused.invalid", model="fake",
                                      timeout_seconds=0.5)
    with pytest.raises(DeepResearchError, match="planner: model timeout"):
        DeepResearchAgent(model=client).run(db, query=QUESTION, vtuber_id="v1")


def test_total_window_budget_across_three_terms(db, monkeypatch):
    for index in range(12):
        add_transcript(db, index * 50_000, index * 50_000 + 1_000,
                       "车祸 演唱 观众", id=f"t{index}")
    calls = []
    original = research.build_investigation_evidence
    def capture(*args, **kwargs):
        bundle = original(*args, **kwargs)
        calls.append((kwargs["max_windows"], len(bundle.windows)))
        return bundle
    monkeypatch.setattr(research, "build_investigation_evidence", capture)
    model = FakeModelClient({"terms": ["车祸", "演唱", "观众"]}, extract_all)
    DeepResearchAgent(model=model).run(
        db, query="车祸和演唱时观众有什么反应？", vtuber_id="v1",
    )
    assert len(calls) == 3
    assert sum(count for _, count in calls) == 8
    assert all(count <= quota for quota, count in calls)
    evidence = json.loads(model.calls[1][-1]["content"])["evidence"]
    ids = [item["evidenceId"] for item in evidence]
    assert len(ids) == len(set(ids))
    assert sum(len(message["content"]) for message in model.calls[1]) <= research.MAX_MODEL_INPUT_CHARS


def test_seed_first_evidence_cap_and_read_only_caller_transaction(db):
    add_transcript(db, 9_000, 9_500, "此前的上下文", id="context")
    add_transcript(db, 10_000, 11_000, "车祸", id="seed")
    assert db.in_transaction
    before = list(db.iterdump())
    report, model = run(db, max_evidence=1)
    evidence = json.loads(model.calls[1][-1]["content"])["evidence"]
    assert [item["evidenceId"] for item in evidence] == ["transcript:seed"]
    assert report.evidence_refs == ["transcript:seed"]
    assert any("截断" in note for note in report.limitations)
    assert db.in_transaction and list(db.iterdump()) == before


def test_cannot_cite_evidence_excluded_from_model_budget(db):
    add_transcript(db, 9_000, 9_500, "上下文", id="context")
    add_transcript(db, 10_000, 11_000, "车祸", id="seed")
    with pytest.raises(CitationGuardError, match="unretrieved"):
        run(db, draft(ref="transcript:context", quote="上下文"), max_evidence=1)


def test_text_cap_and_character_budget(db):
    add_transcript(db, 10_000, 11_000, "车祸" + "字" * 1_200 + "结尾", id="seed")
    report, model = run(db, draft())
    record = json.loads(model.calls[1][-1]["content"])["evidence"][0]
    assert len(record["text"]) == 1_000 and record["textTruncated"]
    assert any("截断" in note for note in report.limitations)
    with pytest.raises(CitationGuardError, match="quotation is not"):
        run(db, draft(quote="结尾"))
    empty_report, tiny_model = run(db, max_evidence_chars=1)
    assert empty_report.evidence_refs == [] and len(tiny_model.calls) == 1


@pytest.mark.parametrize("options", [
    {"max_windows": 0}, {"max_windows": 9}, {"max_windows": True},
    {"max_evidence": 65}, {"max_evidence_chars": 32_001},
])
def test_resource_limits_validated(options):
    with pytest.raises(ValueError):
        DeepResearchAgent(model=FakeModelClient(), **options)


@pytest.mark.parametrize("query, vtuber", [("", "v1"), ("x" * 1_001, "v1"),
                                           (QUESTION, ""), (QUESTION, "unknown")])
def test_invalid_input_before_model_call(db, query, vtuber):
    model = FakeModelClient()
    with pytest.raises(ValueError):
        DeepResearchAgent(model=model).run(db, query=query, vtuber_id=vtuber)
    assert model.calls == []

