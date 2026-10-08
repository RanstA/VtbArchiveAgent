from fastapi.testclient import TestClient
import pytest

from app.config.settings import settings
from app.main import app
from app.repository.reaction_match_repo import get_reaction_match_by_id
from search_fixtures import search_db, seed_topic


@pytest.fixture
def client(search_db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", tmp_path / "search.db")
    with TestClient(app) as client:
        yield client


def test_search_api_returns_camel_case_hits_without_invented_evidence(client, search_db):
    topic = seed_topic(search_db, title="演唱爱情转移", summary="演唱片段摘要")
    before = "\n".join(search_db.iterdump())
    response = client.get("/search/topics", params={"q": "爱情转移", "limit": 5})
    assert response.status_code == 200
    assert response.json() == [{
        "streamId": topic.stream_id, "topicSegmentId": topic.id,
        "startMs": topic.start_ms, "endMs": topic.end_ms,
        "title": topic.title, "snippet": topic.summary, "score": 5.0, "evidenceIds": None,
    }]
    assert "\n".join(search_db.iterdump()) == before


@pytest.mark.parametrize("vtuber_id,expected", [
    (None, ["stream-3", "stream-2", "stream-1"]),
    ("aza", ["stream-2", "stream-1"]),
    (" Izayoi161 ", ["stream-3"]),
    ("unknown", []),
])
def test_search_api_vtuber_filter(client, search_db, vtuber_id, expected):
    for i in range(1, 4):
        seed_topic(search_db, topic_id=f"topic-{i}", stream_id=f"stream-{i}", title="爱情转移")
    params = {"q": "爱情转移"}
    if vtuber_id is not None:
        params["vtuber_id"] = vtuber_id
    response = client.get("/search/topics", params=params)
    assert response.status_code == 200
    assert [item["streamId"] for item in response.json()] == expected


@pytest.mark.parametrize("query", ["", " \t ", "没有命中"])
def test_search_api_empty_results(client, search_db, query):
    seed_topic(search_db)
    response = client.get("/search/topics", params={"q": query})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("params", [
    {}, {"q": "话题", "limit": 0}, {"q": "话题", "limit": -1},
    {"q": "话题", "limit": 101}, {"q": "话题", "limit": "abc"},
    {"q": "话题", "limit": "1.5"}, {"q": "话题", "vtuber_id": ""},
    {"q": "话题", "vtuber_id": "   "},
])
def test_search_api_invalid_parameters(client, params):
    response = client.get("/search/topics", params=params)
    assert response.status_code == 422
    assert response.json()["detail"]


@pytest.mark.parametrize("limit", [1, 100])
def test_search_api_limit_boundaries(client, search_db, limit):
    seed_topic(search_db)
    seed_topic(search_db, topic_id="topic-2", start_ms=105_000)
    response = client.get("/search/topics", params={"q": "话题", "limit": limit})
    assert response.status_code == 200
    assert len(response.json()) == min(limit, 2)


def test_evidence_api_preserves_fields_refs_order_and_local_times(client, search_db):
    topic = seed_topic(search_db, parts=("p1", "p0"))
    before = "\n".join(search_db.iterdump())
    response = client.get(f"/search/topics/{topic.id}/evidence")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"topic", "transcripts", "danmaku"}
    assert payload["topic"] == {
        "id": topic.id, "streamId": topic.stream_id, "sourcePartIds": ["p1", "p0"],
        "reactionMatchIds": topic.reaction_match_ids, "startMs": 101_000, "endMs": 111_000,
        "title": topic.title, "summary": topic.summary, "keywords": [], "entities": [],
        "transcriptSegmentIds": topic.transcript_segment_ids, "salienceScore": 0.9,
        "confidence": 0.8, "analyzerVersion": "test", "topicType": "talk",
    }
    assert [item["id"] for item in payload["transcripts"]] == topic.transcript_segment_ids
    assert payload["transcripts"][0] == {
        "id": "stream-1-p1-t1", "streamId": "stream-1", "partId": "p1",
        "startMs": 3_000, "endMs": 4_000, "rawText": " 原始转写 1 ",
        "text": "转写 1", "source": "test",
    }
    matches = [get_reaction_match_by_id(search_db, ref) for ref in topic.reaction_match_ids]
    expected_ids = list(dict.fromkeys(ref for match in matches for ref in match.danmaku_ids))
    assert [item["id"] for item in payload["danmaku"]] == expected_ids
    assert payload["danmaku"][0] == {
        "id": expected_ids[0], "streamId": "stream-1", "partId": "p1",
        "timestampMs": 3_500, "rawText": "{style}弹幕 2", "text": "弹幕 2",
    }
    assert all(item["streamId"] == topic.stream_id for item in [*payload["transcripts"], *payload["danmaku"]])
    assert "\n".join(search_db.iterdump()) == before


def test_evidence_api_missing_topic_is_404(client):
    response = client.get("/search/topics/missing/evidence")
    assert response.status_code == 404
    assert response.json() == {"detail": "TopicSegment not found: missing"}


@pytest.mark.parametrize("sql,message", [
    ("UPDATE topic_segment_reaction_matches SET reaction_match_id = 'missing' WHERE position = 0",
     "ReactionMatch not found"),
    ("UPDATE topic_segment_transcripts SET transcript_segment_id = 'missing' WHERE position = 0",
     "TranscriptSegment not found"),
    ("UPDATE reaction_match_danmaku SET danmaku_id = 999999 WHERE reaction_match_id = 'stream-1-p1-m0' AND position = 0",
     "Danmaku not found"),
    ("UPDATE transcript_segments SET stream_id = 'stream-3' WHERE id = 'stream-1-p1-t1'",
     "TranscriptSegment StreamPart/reference mismatch"),
    ("DELETE FROM topic_segment_transcripts", "Invalid TopicSegment"),
])
def test_evidence_api_inconsistent_archive_is_409_not_partial_success(client, search_db, sql, message):
    seed_topic(search_db)
    search_db.execute("PRAGMA foreign_keys = OFF")
    search_db.execute(sql)
    search_db.commit()
    response = client.get("/search/topics/topic-1/evidence")
    assert response.status_code == 409
    assert message in response.json()["detail"]
    assert set(response.json()) == {"detail"}
