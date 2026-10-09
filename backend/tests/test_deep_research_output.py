"""Structured-output reliability without network calls or permissive JSON repair."""
import json
import logging

import httpx
import pytest
from pydantic import ValidationError

import app.investigation.deep_research as research
from app.investigation.deep_research import DeepResearchAgent
from app.investigation.deep_research_models import (
    CitationGuardError, DeepResearchError, ResearchDraft, StructuredOutputError,
)
from app.investigation.model_client import ModelClientError, OpenAICompatibleChatClient
from test_deep_research import FakeModelClient, QUESTION, draft
from test_investigation_evidence import db, add_transcript


VALID_DRAFT = {"findings": [], "insufficientEvidence": True}


def message(value):
    return {"content": json.dumps(value, ensure_ascii=False)}


class MessageModel:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, *, messages, tools=None):
        self.calls.append(messages)
        assert self.responses, "unexpected retry"
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def ask(model):
    return DeepResearchAgent(model=model)._ask(
        "report", "Return strict JSON.", {"evidence": [], "question": QUESTION}, ResearchDraft,
    )


FORMAT_CASES = [
    ({"content": '{"findings":'}, "json_syntax"),
    (message({"findings": []}), "schema_validation"),
    (message({**VALID_DRAFT, "extra": "not allowed"}), "schema_validation"),
    (message({"findings": [], "insufficientEvidence": "true"}), "schema_validation"),
    ({"content": chr(96) * 3 + "json\n" + json.dumps(VALID_DRAFT) + "\n" + chr(96) * 3},
     "markdown_wrapper"),
    ({"content": ""}, "empty_response"),
    ({"content": " \n "}, "empty_response"),
    ({"content": None}, "empty_response"),
    ({}, "empty_response"),
    ({"content": []}, "non_string_response"),
    ({"content": {}}, "non_string_response"),
    ({"content": 42}, "non_string_response"),
    ({"content": '{"findings":', "_finish_reason": "length"}, "output_truncated"),
    ({**message(VALID_DRAFT), "_finish_reason": "length"}, "output_truncated"),
    ({"content": "x" * (research.MAX_MODEL_RESPONSE_CHARS + 1)}, "response_too_large"),
    ({"content": '{"findings":[],"findings":[],"insufficientEvidence":true}'}, "json_syntax"),
    ({"content": '{"findings":NaN,"insufficientEvidence":true}'}, "json_syntax"),
]


@pytest.mark.parametrize("invalid, category", FORMAT_CASES)
def test_format_failure_then_success_uses_same_evidence_and_strict_schema(invalid, category, caplog):
    model = MessageModel(invalid, message(VALID_DRAFT))
    with caplog.at_level(logging.WARNING, logger=research.__name__):
        result = ask(model)
    assert result.insufficient_evidence is True
    assert len(model.calls) == 2
    assert model.calls[0][1] == model.calls[1][1]
    correction = model.calls[1][0]["content"]
    assert category in correction
    assert "不得增加字段或转换字段类型" in correction
    assert "不要修改 evidenceRef 或 quote" in correction
    assert f"stage=report attempt=1 error_type={category}" in caplog.text
    assert len(caplog.records) == 1


@pytest.mark.parametrize("invalid, category", FORMAT_CASES)
def test_two_failures_are_diagnosed_without_third_attempt(invalid, category, caplog):
    model = MessageModel(invalid, invalid, message(VALID_DRAFT))
    with caplog.at_level(logging.WARNING, logger=research.__name__):
        with pytest.raises(StructuredOutputError) as caught:
            ask(model)
    assert caught.value.stage == "report"
    assert caught.value.error_type == category
    assert caught.value.attempt == 2
    assert category in str(caught.value)
    assert "attempts=2" in str(caught.value)
    assert len(model.calls) == 2
    assert len(model.responses) == 1
    assert len(caplog.records) == 2
    assert all(record.exc_info is None for record in caplog.records)


def test_schema_diagnostics_log_paths_not_values_or_unknown_keys(caplog):
    secret = "PRIVATE_EVIDENCE_OR_KEY"
    invalid = message({
        "findings": [{"kind": secret, "citations": [{"evidenceRef": secret, "quote": 123}]}],
        "insufficientEvidence": secret,
        secret: secret,
    })
    model = MessageModel(invalid, invalid)
    with caplog.at_level(logging.WARNING, logger=research.__name__):
        with pytest.raises(StructuredOutputError) as caught:
            ask(model)
    assert "findings.0.kind:literal_error" in caplog.text
    assert "findings.0.citations.0.quote:string_type" in caplog.text
    assert "insufficientEvidence:bool_type" in caplog.text
    assert "<extra>:extra_forbidden" in caplog.text
    assert secret not in caplog.text
    assert secret not in str(caught.value)
    assert secret not in model.calls[1][0]["content"]


def test_missing_fields_named_in_retry_feedback():
    model = MessageModel(message({"findings": []}), message(VALID_DRAFT))
    ask(model)
    assert "insufficientEvidence:missing" in model.calls[1][0]["content"]


@pytest.mark.parametrize("invalid, category", [
    ([], "invalid_response"),
    ({"content": "private", "tool_calls": [{"id": "private"}]}, "unexpected_tool_calls"),
    ({"content": None, "refusal": "private refusal"}, "model_refusal"),
    ({"content": "", "_finish_reason": "content_filter"}, "model_refusal"),
])
def test_nonrecoverable_messages_never_retry(invalid, category):
    model = MessageModel(invalid, message(VALID_DRAFT))
    with pytest.raises(StructuredOutputError) as caught:
        ask(model)
    assert caught.value.error_type == category
    assert caught.value.attempt == 1
    assert len(model.calls) == 1


@pytest.mark.parametrize("failure", [ModelClientError("private"), TimeoutError("private"),
                                      httpx.ReadTimeout("private")])
def test_transport_errors_never_retry(failure, caplog):
    model = MessageModel(failure, message(VALID_DRAFT))
    with pytest.raises(DeepResearchError):
        ask(model)
    assert len(model.calls) == 1
    assert "private" not in caplog.text


def test_retry_rechecks_model_input_budget(monkeypatch):
    probe = MessageModel(message(VALID_DRAFT))
    ask(probe)
    initial_size = sum(len(item["content"]) for item in probe.calls[0])
    monkeypatch.setattr(research, "MAX_MODEL_INPUT_CHARS", initial_size)
    model = MessageModel({"content": "broken"}, message(VALID_DRAFT))
    with pytest.raises(DeepResearchError, match="input exceeds"):
        ask(model)
    assert len(model.calls) == 1


def test_both_stages_can_recover_but_total_calls_are_bounded(db):
    add_transcript(db, 10_000, 11_000, "车祸", id="seed")
    model = FakeModelClient("broken", {"terms": ["车祸"]}, "broken", draft())
    report = DeepResearchAgent(model=model).run(db, query=QUESTION, vtuber_id="v1")
    assert report.evidence_refs == ["transcript:seed"]
    assert report.findings[0].citations[0].quote == "车祸"
    assert len(model.calls) == 4


@pytest.mark.parametrize("bad_draft", [
    draft(ref="transcript:forged"),
    draft(quote="主播承认发生了交通事故"),
    draft(kind="audience_reaction"),
])
@pytest.mark.parametrize("initial_format_failure", [False, True])
def test_guard_failure_never_repairs_citations_or_triggers_another_call(
    db, bad_draft, initial_format_failure,
):
    add_transcript(db, 10_000, 11_000, "车祸", id="seed")
    replies = [{"terms": ["车祸"]}]
    if initial_format_failure:
        replies.append("broken")
    replies.extend([bad_draft, draft()])
    model = FakeModelClient(*replies)
    with pytest.raises(CitationGuardError):
        DeepResearchAgent(model=model).run(db, query=QUESTION, vtuber_id="v1")
    assert len(model.calls) == 2 + int(initial_format_failure)
    assert len(model.replies) == 1


def test_semantically_invalid_plan_does_not_retry():
    model = FakeModelClient({"terms": [QUESTION]}, {"terms": ["车祸"]})
    with pytest.raises(DeepResearchError, match="expected distinct extracted keywords"):
        DeepResearchAgent(model=model).plan_query(QUESTION)
    assert len(model.calls) == 1


def test_client_metadata_is_opt_in_and_request_parameters_unchanged(monkeypatch):
    requests = []
    original_message = {"role": "assistant", "content": '{"findings":'}
    def post(url, **kwargs):
        requests.append(kwargs)
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "choices": [{"message": original_message, "finish_reason": "length"}],
        })
    monkeypatch.setattr(httpx, "post", post)
    client = OpenAICompatibleChatClient(base_url="https://unused.invalid/v1",
                                      model="fake", api_key="PRIVATE_API_KEY")
    messages = [{"role": "user", "content": "JSON"}]
    assert client.complete(messages=messages) == original_message
    enriched = client.complete(messages=messages, include_finish_reason=True)
    assert enriched == {**original_message, "_finish_reason": "length"}
    assert requests[0]["json"] == requests[1]["json"]
    assert "response_format" not in requests[1]["json"]
    assert "include_finish_reason" not in requests[1]["json"]
    assert requests[1]["headers"]["Authorization"] == "Bearer PRIVATE_API_KEY"
    assert "_finish_reason" not in original_message


def test_real_client_finish_metadata_reaches_agent_without_network(monkeypatch, caplog):
    calls = []
    def post(url, **kwargs):
        calls.append(kwargs)
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "choices": [{"message": {"content": "PRIVATE_TRUNCATED_EVIDENCE"},
                         "finish_reason": "length"}],
        })
    monkeypatch.setattr(httpx, "post", post)
    client = OpenAICompatibleChatClient(base_url="https://unused.invalid/v1",
                                      model="fake", api_key="PRIVATE_API_KEY")
    with caplog.at_level(logging.WARNING, logger=research.__name__):
        with pytest.raises(StructuredOutputError, match="output_truncated"):
            ask(client)
    assert len(calls) == 2
    assert "PRIVATE" not in caplog.text
    assert "PRIVATE_TRUNCATED_EVIDENCE" not in calls[1]["json"]["messages"][0]["content"]


def test_schema_is_not_weakened():
    with pytest.raises(ValidationError):
        ResearchDraft.model_validate({"findings": [], "insufficientEvidence": "true"})
