from app.domain.event import Event
from app.retrieval.bm25 import (
    BM25EventRetriever,
    tokenize,
)


def make_event(
    *,
    event_id: str,
    title: str,
    summary: str,
    keywords: list[str],
) -> Event:
    semantic_text = "\n".join(
        [
            title,
            summary,
            *keywords,
        ]
    )

    return Event(
        id=event_id,
        stream_id="stream-1",
        part_id="part-1",
        start_ms=0,
        end_ms=30_000,
        peak_ms=15_000,
        source_highlight_ids=[
            f"highlight-{event_id}",
        ],
        title=title,
        summary=summary,
        keywords=keywords,
        entities=[],
        semantic_text=semantic_text,
        semanticizer_version="v1",
    )


def test_tokenize_chinese_query():
    tokens = tokenize(
        "他聊过猫吗"
    )

    assert "猫" in tokens
    assert "聊过" in tokens


def test_bm25_ranks_relevant_event_first():
    events = [
        make_event(
            event_id="cat",
            title="观众讨论猫",
            summary="弹幕集中出现猫和宠物相关讨论。",
            keywords=[
                "猫",
                "宠物",
            ],
        ),
        make_event(
            event_id="game",
            title="观众讨论游戏失败",
            summary="弹幕集中讨论游戏中的失败情境。",
            keywords=[
                "游戏",
                "失败",
            ],
        ),
        make_event(
            event_id="singing",
            title="观众讨论唱歌",
            summary="弹幕集中讨论歌曲和演唱。",
            keywords=[
                "唱歌",
                "歌曲",
            ],
        ),
    ]

    retriever = BM25EventRetriever(
        events
    )

    results = retriever.search(
        "他以前聊过猫吗？",
        top_k=3,
    )

    assert results
    assert results[0].event.id == "cat"
    assert results[0].score > 0


def test_bm25_respects_top_k():
    events = [
        make_event(
            event_id="cat-1",
            title="猫",
            summary="讨论猫。",
            keywords=["猫"],
        ),
        make_event(
            event_id="cat-2",
            title="猫咪",
            summary="讨论猫咪。",
            keywords=["猫"],
        ),
    ]

    retriever = BM25EventRetriever(
        events
    )

    results = retriever.search(
        "猫",
        top_k=1,
    )

    assert len(results) == 1


def test_bm25_returns_empty_for_unmatched_query():
    event = make_event(
        event_id="cat",
        title="观众讨论猫",
        summary="弹幕讨论猫。",
        keywords=["猫"],
    )

    retriever = BM25EventRetriever(
        [event]
    )

    results = retriever.search(
        "量子力学",
    )

    assert results == []