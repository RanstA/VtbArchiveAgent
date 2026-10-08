import pytest

from app.product.search import SearchHit
from app.product.topic_search import search_topics
from search_fixtures import search_db, seed_topic


@pytest.mark.parametrize("fields,score", [
    ({"title": "演唱爱情转移"}, 5),
    ({"summary": "听到爱情转移"}, 2),
    ({"keywords": ["爱情转移", "演唱爱情转移"]}, 4),
    ({"entities": ["爱情转移", "歌曲爱情转移"]}, 4),
    ({"title": "爱情转移", "summary": "爱情转移",
      "keywords": ["爱情转移"], "entities": ["爱情转移"]}, 15),
])
def test_search_field_weights_and_hit_projection(search_db, fields, score):
    topic = seed_topic(search_db, **fields)
    hits = search_topics(search_db, "  爱情转移  ")
    assert len(hits) == 1
    hit = hits[0]
    assert isinstance(hit, SearchHit)
    assert hit.score == score
    assert hit.stream_id == topic.stream_id
    assert hit.topic_segment_id == topic.id
    assert (hit.start_ms, hit.end_ms) == (topic.start_ms, topic.end_ms)
    assert (hit.title, hit.snippet) == (topic.title, topic.summary)
    assert hit.evidence_ids is None


def test_search_orders_score_then_live_time_then_start(search_db):
    seed_topic(search_db, topic_id="low-recent", stream_id="stream-3", summary="命中")
    seed_topic(search_db, topic_id="high-old", title="命中")
    seed_topic(search_db, topic_id="middle-old", stream_id="stream-2", keywords=["命中"])
    seed_topic(search_db, topic_id="middle-later", stream_id="stream-3",
               start_ms=105_000, entities=["命中"])
    seed_topic(search_db, topic_id="middle-earlier", stream_id="stream-3",
               start_ms=101_000, keywords=["命中"])
    assert [hit.topic_segment_id for hit in search_topics(search_db, "命中")] == [
        "high-old", "middle-earlier", "middle-later", "middle-old", "low-recent",
    ]


@pytest.mark.parametrize("vtuber_id,expected", [
    (None, ["stream-3", "stream-2", "stream-1"]),
    ("aza", ["stream-2", "stream-1"]),
    ("Izayoi161", ["stream-3"]),
    ("unknown", []),
])
def test_search_cross_stream_and_vtuber_filter(search_db, vtuber_id, expected):
    for i in range(1, 4):
        seed_topic(search_db, topic_id=f"topic-{i}", stream_id=f"stream-{i}", title="共同话题")
    assert [hit.stream_id for hit in search_topics(
        search_db, "共同话题", vtuber_id=vtuber_id,
    )] == expected


def test_search_limit_and_default(search_db):
    for i in range(6):
        seed_topic(search_db, topic_id=f"topic-{i}", start_ms=101_000 + i * 1_000)
    assert len(search_topics(search_db, "话题")) == 5
    assert len(search_topics(search_db, "话题", limit=1)) == 1
    assert len(search_topics(search_db, "话题", limit=100)) == 6


@pytest.mark.parametrize("limit", [-1, 0, 101])
@pytest.mark.parametrize("query", ["话题", ""])
def test_search_rejects_out_of_range_limit(search_db, limit, query):
    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        search_topics(search_db, query, limit=limit)


@pytest.mark.parametrize("query", ["", " \t\n", "没有命中", "%", "_", "' OR 1=1 --"])
def test_search_empty_or_nonmatching_literal_query(search_db, query):
    seed_topic(search_db)
    assert search_topics(search_db, query) == []
