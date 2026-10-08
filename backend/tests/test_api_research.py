"""HTTP contract tests run the real DeepResearch agent with a scripted model."""
import sqlite3

from fastapi.testclient import TestClient
import httpx
import pytest

import app.api.investigate as api
from app.config.settings import Settings, settings
from app.main import app
from app.investigation.model_client import ModelClientError
from search_fixtures import search_db, seed_topic
from test_deep_research import FakeModelClient, draft, extract_all
from test_investigation_evidence import add_transcript, add_danmaku


QUESTION = "主播有没有提到车祸？"
PAYLOAD = {"vtuberId": "aza", "query": QUESTION}


@pytest.fixture
def client(search_db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "deep_research_dev_enabled", True)
    monkeypatch.setattr(settings, "database_path", tmp_path / "search.db")
    monkeypatch.setattr(settings, "event_scout_api_base_url", "https://unused.invalid/v1")
    monkeypatch.setattr(settings, "event_scout_model", "fake-model")
    monkeypatch.setattr(settings, "event_scout_api_key", "fake-key")
    monkeypatch.setattr(settings, "event_scout_timeout_seconds", 3.0)
    with TestClient(app, client=("127.0.0.1", 54321)) as client:
        yield client


@pytest.fixture
def install_model(monkeypatch):
    def install(*replies):
        model = FakeModelClient(*replies)
        configurations = []
        def create(**kwargs):
            configurations.append(kwargs)
            return model
        monkeypatch.setattr(api, "OpenAICompatibleChatClient", create)
        return model, configurations
    return install


def seed_speech(db, *, stream_id="stream-1", id="seed"):
    add_transcript(db, 20_000, 22_000, "刚才提到车祸这个词",
                   stream_id=stream_id, part_id="p1", id=id)
    db.commit()


def test_research_camel_case_contract_and_read_only_db(client, search_db, install_model, monkeypatch):
    seed_speech(search_db)
    seed_speech(search_db, stream_id="stream-3", id="other-vtuber")
    model, configs = install_model({"terms": ["车祸"]}, draft(quote="刚才提到车祸这个词"))
    before = list(search_db.iterdump())
    closed = []
    original_connect = sqlite3.connect
    class TrackingConnection(sqlite3.Connection):
        def close(self):
            super().close()
            # Verify closure in FastAPI's worker, not from the test thread.
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                self.execute("SELECT 1")
            closed.append(True)
    def tracked_connect(*args, **kwargs):
        return original_connect(*args, **kwargs, factory=TrackingConnection)
    monkeypatch.setattr(api.sqlite3, "connect", tracked_connect)
    original = api.DeepResearchAgent.run
    def checked_run(self, connection, **kwargs):
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("UPDATE streams SET title = 'must not write'")
        return original(self, connection, **kwargs)
    monkeypatch.setattr(api.DeepResearchAgent, "run", checked_run)
    response = client.post("/investigate/research", json=PAYLOAD)
    assert response.status_code == 200, response.text
    report = response.json()
    assert set(report) == {"query", "vtuberId", "searchTerms", "answer", "findings",
                           "evidenceRefs", "locations", "limitations"}
    assert report["vtuberId"] == "aza"
    assert report["searchTerms"] == ["车祸"]
    assert report["evidenceRefs"] == ["transcript:seed"]
    assert report["findings"] == [{
        "kind": "speech",
        "statement": "字幕转写记载：“刚才提到车祸这个词”〔transcript:seed〕",
        "evidenceRefs": ["transcript:seed"],
        "citations": [{"evidenceRef": "transcript:seed", "quote": "刚才提到车祸这个词"}],
    }]
    assert report["locations"] == [{
        "evidenceRef": "transcript:seed", "streamId": "stream-1",
        "sourcePartIds": ["p1"], "partId": "p1", "localStartMs": 20_000,
        "localEndMs": 22_000, "streamStartMs": 120_000, "streamEndMs": 122_000,
    }]
    assert report["answer"] and report["limitations"]
    assert "trace" not in report and "candidates" not in report
    assert len(model.calls) == 2
    assert "other-vtuber" not in model.calls[1][-1]["content"]
    assert configs == [{
        "base_url": "https://unused.invalid/v1", "model": "fake-model",
        "api_key": "fake-key", "timeout_seconds": 3.0,
    }]
    assert list(search_db.iterdump()) == before
    assert closed == [True]


def test_api_topic_preserves_global_time_and_unknown_local_range(client, search_db, install_model):
    seed_topic(search_db, title="车祸话题", parts=("p0", "p1"))
    install_model({"terms": ["车祸"]}, extract_all)
    report = client.post("/investigate/research", json=PAYLOAD).json()
    assert report["findings"][0]["kind"] == "archived_interpretation"
    location = report["locations"][0]
    assert location["sourcePartIds"] == ["p0", "p1"]
    assert location["localStartMs"] is None and location["partId"] is None
    assert location["streamStartMs"] == 101_000


def test_api_danmaku_is_audience_not_speech(client, search_db, install_model):
    row_id = add_danmaku(search_db, 20_000, "车祸", stream_id="stream-1", part_id="p1")
    search_db.commit()
    install_model({"terms": ["车祸"]}, draft("audience_reaction", f"danmaku:{row_id}"))
    response = client.post("/investigate/research", json=PAYLOAD)
    assert response.status_code == 200
    assert response.json()["findings"][0]["kind"] == "audience_reaction"
    assert any("不能据此确认主播" in note for note in response.json()["limitations"])


def test_api_no_evidence_has_explicit_empty_report(client, install_model):
    model, _ = install_model({"terms": ["车祸"]})
    response = client.post("/investigate/research", json=PAYLOAD)
    assert response.status_code == 200
    report = response.json()
    assert report["findings"] == report["locations"] == report["evidenceRefs"] == []
    assert "证据不足" in report["answer"]
    assert len(model.calls) == 1


@pytest.mark.parametrize("payload", [
    {}, {"query": QUESTION}, {"vtuberId": "aza"}, {"vtuberId": "", "query": QUESTION},
    {"vtuberId": "   ", "query": QUESTION}, {"vtuberId": "aza", "query": "  "},
    {"vtuberId": "aza", "query": "x" * 1001}, {"vtuberId": "aza", "query": 123},
    {**PAYLOAD, "unknown": True},
])
def test_invalid_requests_fail_before_model(client, install_model, payload):
    model, _ = install_model()
    assert client.post("/investigate/research", json=payload).status_code == 422
    assert model.calls == []


def test_disabled_by_default(client, install_model, monkeypatch):
    assert Settings.model_fields["deep_research_dev_enabled"].default is False
    monkeypatch.setattr(settings, "deep_research_dev_enabled", False)
    model, configs = install_model()
    response = client.post("/investigate/research", json=PAYLOAD)
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "research_disabled"
    assert configs == model.calls == []


def test_remote_request_rejected_even_when_enabled(client, install_model):
    model, configs = install_model()
    with TestClient(app, client=("203.0.113.9", 54321)) as remote:
        response = remote.post("/investigate/research", json=PAYLOAD,
                               headers={"X-Forwarded-For": "127.0.0.1"})
    assert response.status_code == 403
    assert configs == model.calls == []


def test_ipv6_loopback_supported(client, install_model):
    install_model({"terms": ["车祸"]})
    with TestClient(app, client=("::1", 54321)) as local:
        assert local.post("/investigate/research", json=PAYLOAD).status_code == 200


def test_unconfigured_model(client, install_model, monkeypatch):
    monkeypatch.setattr(settings, "event_scout_model", None)
    model, _ = install_model()
    response = client.post("/investigate/research", json=PAYLOAD)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "model_not_configured"
    assert model.calls == []


def test_unknown_vtuber(client, install_model):
    model, _ = install_model()
    response = client.post("/investigate/research", json={**PAYLOAD, "vtuberId": "missing"})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "vtuber_not_found"
    assert model.calls == []


@pytest.mark.parametrize("reply, code, status", [
    (draft(ref="transcript:forged"), "citation_validation_failed", 502),
    (draft("audience_reaction"), "citation_validation_failed", 502),
    ('{"broken"', "research_failed", 502),
    (ModelClientError("sensitive upstream details"), "research_failed", 502),
    (httpx.ReadTimeout("upstream timeout"), "model_timeout", 504),
])
def test_model_and_citation_failures_return_no_partial_report(
    client, search_db, install_model, reply, code, status,
):
    seed_speech(search_db)
    install_model({"terms": ["车祸"]}, reply)
    response = client.post("/investigate/research", json=PAYLOAD)
    assert response.status_code == status
    assert set(response.json()) == {"detail"}
    assert response.json()["detail"]["code"] == code
    assert "sensitive upstream" not in response.text


def test_invalid_planner_is_explicit(client, install_model):
    install_model({"terms": [QUESTION]})
    response = client.post("/investigate/research", json=PAYLOAD)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "research_failed"


def test_httpx_timeout_with_lower_level_cause_stays_504(client, search_db, install_model):
    seed_speech(search_db)
    timeout = httpx.ReadTimeout("wrapped transport timeout")
    timeout.__cause__ = OSError("low-level transport failure")
    install_model({"terms": ["车祸"]}, timeout)
    response = client.post("/investigate/research", json=PAYLOAD)
    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "model_timeout"


def test_missing_database_does_not_create_file(client, install_model, tmp_path, monkeypatch):
    path = tmp_path / "does-not-exist.db"
    monkeypatch.setattr(settings, "database_path", path)
    install_model()
    response = client.post("/investigate/research", json=PAYLOAD)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "archive_unavailable"
    assert not path.exists()


def test_existing_stream_highlights_api_preserved(client):
    response = client.get("/streams/stream-1/highlights")
    assert response.status_code == 200 and len(response.json()) == 6
