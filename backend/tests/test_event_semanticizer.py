import json

import pytest
from pydantic import ValidationError

from app.event_pipeline.events import (
    EventCandidate,
)
from app.event_pipeline.semanticizer import (
    EventSemanticizer,
    EventSemanticizerDraft,
    EventSemanticizerError,
    EventSemanticizerInput,
    build_semantic_text,
    build_user_message,
)
def make_candidate() -> EventCandidate:
    return EventCandidate(
        stream_id="stream-1",
        part_id="part-1",
        start_ms=1000,
        end_ms=5000,
        peak_ms=3000,
        source_highlight_ids=[
            "highlight-1",
        ],
    )


def test_build_semantic_text():
    draft = EventSemanticizerDraft(
        title="观众集中讨论猫",
        summary="弹幕中多次出现猫相关讨论。",
        keywords=[
            "猫",
            "宠物",
        ],
        entities=[
            "蜜言",
        ],
    )

    result = build_semantic_text(
        draft
    )

    assert result == (
        "观众集中讨论猫\n"
        "弹幕中多次出现猫相关讨论。\n"
        "猫\n"
        "宠物\n"
        "蜜言"
    )


def test_build_semantic_text_skips_empty_items():
    draft = EventSemanticizerDraft(
        title="事件标题",
        summary="事件摘要",
        keywords=[
            "",
            "猫",
            "   ",
        ],
        entities=[],
    )

    result = build_semantic_text(
        draft
    )

    assert result == (
        "事件标题\n"
        "事件摘要\n"
        "猫"
    )


def test_build_user_message_contains_evidence():
    semanticizer_input = (
        EventSemanticizerInput(
            candidate=make_candidate(),
            stream_title="测试直播",
            danmaku_texts=[
                "哈哈哈哈",
                "你又死了",
            ],
        )
    )

    message = build_user_message(
        semanticizer_input
    )

    payload = json.loads(
        message
    )

    assert payload["streamTitle"] == "测试直播"

    assert payload["event"]["startMs"] == 1000
    assert payload["event"]["endMs"] == 5000
    assert payload["event"]["peakMs"] == 3000

    assert payload["danmaku"] == [
        "哈哈哈哈",
        "你又死了",
    ]


def test_semanticizer_input_requires_danmaku():
    with pytest.raises(
        ValidationError
    ):
        EventSemanticizerInput(
            candidate=make_candidate(),
            stream_title="测试直播",
            danmaku_texts=[],
        )
        
class FakeModel:
    def __init__(self) -> None:
        self.calls = []

    def complete(
        self,
        *,
        messages,
        tools=None,
    ):
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
            }
        )

        return {
            "content": json.dumps(
                {
                    "title": "观众集中讨论猫",
                    "summary": "弹幕中多次出现猫相关讨论。",
                    "keywords": [
                        "猫",
                        "宠物",
                    ],
                    "entities": [
                        "蜜言",
                    ],
                },
                ensure_ascii=False,
            )
        }


def test_semanticizer_calls_model_once_and_builds_event():
    model = FakeModel()

    semanticizer = EventSemanticizer(
        model=model,
    )

    semanticizer_input = EventSemanticizerInput(
        candidate=make_candidate(),
        stream_title="测试直播",
        danmaku_texts=[
            "猫猫",
            "养猫吗",
            "可爱",
        ],
    )

    event = semanticizer.semanticize(
        semanticizer_input
    )

    assert len(model.calls) == 1
    assert model.calls[0]["tools"] is None

    assert event.stream_id == "stream-1"
    assert event.part_id == "part-1"

    assert event.title == "观众集中讨论猫"
    assert event.summary == "弹幕中多次出现猫相关讨论。"

    assert event.keywords == [
        "猫",
        "宠物",
    ]

    assert event.entities == [
        "蜜言",
    ]

    assert event.semantic_text == (
        "观众集中讨论猫\n"
        "弹幕中多次出现猫相关讨论。\n"
        "猫\n"
        "宠物\n"
        "蜜言"
    )

    assert event.semanticizer_version == "v1"

    assert event.source_highlight_ids == [
        "highlight-1",
    ]
    
def test_semanticizer_rejects_invalid_json():
    class InvalidJsonModel:
        def complete(
            self,
            *,
            messages,
            tools=None,
        ):
            return {
                "content": "not valid json"
            }

    semanticizer = EventSemanticizer(
        model=InvalidJsonModel(),
    )

    semanticizer_input = EventSemanticizerInput(
        candidate=make_candidate(),
        stream_title="测试直播",
        danmaku_texts=[
            "哈哈哈哈",
        ],
    )

    with pytest.raises(
        EventSemanticizerError,
        match=(
            "Event Semanticizer response "
            "is not valid structured JSON"
        ),
    ):
        semanticizer.semanticize(
            semanticizer_input
        )