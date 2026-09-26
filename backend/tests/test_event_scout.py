import json
from typing import Any
import pytest
from app.investigation.event_scout import EventScout, EventScoutError


class ScriptedModel:
    """
    按预先定义的顺序返回模型响应。

    用于测试 Agent Runtime，
    避免依赖真实 LLM API。
    """

    def __init__(
        self,
        responses: list[dict[str, Any]],
    ) -> None:
        self.responses = list(responses)
        self.call_count = 0

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        response = self.responses[self.call_count]
        self.call_count += 1
        return response


class FakeEventScoutTools:
    """
    Event Scout 测试用工具集合。

    不访问 SQLite，
    直接返回固定 Highlight 和 Danmaku 数据。
    """

    def __init__(self) -> None:
        self.calls: list[
            tuple[str, dict[str, Any]]
        ] = []

    def tool_schemas(
        self,
    ) -> list[dict[str, Any]]:
        return []

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict:
        self.calls.append(
            (
                name,
                arguments,
            )
        )

        if name == "search_highlights":
            return {
                "vtuber_id": "aza",
                "candidate_count": 1,
                "candidates": [
                    {
                        "highlight_id": "highlight-1",
                        "stream_id": "stream-1",
                        "stream_title": "测试直播",
                        "live_time": "2026-09-01T20:00:00",
                        "part_id": "part-1",
                        "start_ms": 10000,
                        "end_ms": 40000,
                        "peak_ms": 25000,
                        "score": 0.95,
                    }
                ],
            }

        if name == "get_danmaku_window":
            return {
                "highlight_id": "highlight-1",
                "danmaku": [
                    {
                        "id": 101,
                        "timestamp_ms": 20000,
                        "text": "哈哈哈哈",
                    },
                    {
                        "id": 102,
                        "timestamp_ms": 21000,
                        "text": "笑死",
                    },
                ],
            }

        raise ValueError(
            f"unexpected tool: {name}"
        )


def test_event_scout_happy_path():
    model = ScriptedModel(
        responses=[
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-search",
                        "type": "function",
                        "function": {
                            "name": "search_highlights",
                            "arguments": json.dumps(
                                {
                                    "top_k": 5,
                                }
                            ),
                        },
                    }
                ],
            },
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-danmaku",
                        "type": "function",
                        "function": {
                            "name": "get_danmaku_window",
                            "arguments": json.dumps(
                                {
                                    "highlight_id": "highlight-1",
                                }
                            ),
                        },
                    }
                ],
            },
            {
                "content": json.dumps(
                    {
                        "answer": "发现一个观众反应明显的片段。",
                        "findings": [
                            {
                                "highlight_id": "highlight-1",
                                "observation": (
                                    "该时间段出现大量"
                                    "笑声相关弹幕。"
                                ),
                                "interpretation": (
                                    "该片段可能引发了"
                                    "观众集中互动。"
                                ),
                                "confidence": 0.9,
                                "danmaku_ids": [
                                    101,
                                    102,
                                ],
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            },
        ]
    )

    tools = FakeEventScoutTools()

    scout = EventScout(
        model=model,
        tools=tools,
    )

    result = scout.run(
        query="最近有没有观众反应特别明显的片段？",
        vtuber_id="aza",
    )

    assert result.query == (
        "最近有没有观众反应特别明显的片段？"
    )

    assert result.vtuber_id == "aza"

    assert len(
        result.findings
    ) == 1

    finding = result.findings[0]

    assert finding.highlight_id == "highlight-1"

    assert finding.observation == (
        "该时间段出现大量笑声相关弹幕。"
    )

    assert finding.interpretation == (
        "该片段可能引发了观众集中互动。"
    )

    assert finding.confidence == 0.9

    assert [
        evidence.id
        for evidence in finding.evidence
    ] == [
        "highlight:highlight-1",
        "danmaku:101",
        "danmaku:102",
    ]

    assert [
        name
        for name, _
        in tools.calls
    ] == [
        "search_highlights",
        "get_danmaku_window",
    ]

    assert [
        step.action
        for step in result.trace
    ] == [
        "model",
        "tool",
        "model",
        "tool",
        "model",
        "final",
    ]
    
    
    
def test_finding_without_danmaku_fetch_is_dropped():
    """
    Highlight 虽然经过 search_highlights 被检索到，
    但如果 Agent 没有进一步调用 get_danmaku_window，
    就不能进入最终 Finding。

    用于保证：
    最终 Finding 必须具有实际弹幕 Evidence。
    """

    model = ScriptedModel(
        responses=[
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-search",
                        "type": "function",
                        "function": {
                            "name": "search_highlights",
                            "arguments": json.dumps(
                                {
                                    "top_k": 5,
                                }
                            ),
                        },
                    }
                ],
            },

            # 模型没有调用 get_danmaku_window，
            # 直接尝试生成最终 Finding。
            {
                "content": json.dumps(
                    {
                        "answer": "发现一个可能值得关注的片段。",
                        "findings": [
                            {
                                "highlight_id": "highlight-1",
                                "observation": (
                                    "该时间段出现大量"
                                    "笑声相关弹幕。"
                                ),
                                "interpretation": (
                                    "该片段可能引发了"
                                    "观众集中互动。"
                                ),
                                "confidence": 0.9,
                                "danmaku_ids": [
                                    101,
                                    102,
                                ],
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            },
        ]
    )

    tools = FakeEventScoutTools()

    scout = EventScout(
        model=model,
        tools=tools,
    )

    result = scout.run(
        query="有没有观众反应明显的片段？",
        vtuber_id="aza",
    )

    # Highlight 虽然被 search_highlights 找到，
    # 但没有真正获取 Danmaku Evidence，
    # 因此不能进入最终结果。
    assert result.findings == []

    # Runtime 实际只执行了 search_highlights。
    assert [
        name
        for name, _
        in tools.calls
    ] == [
        "search_highlights",
    ]

    assert [
        step.action
        for step in result.trace
    ] == [
        "model",
        "tool",
        "model",
        "final",
    ]    
    

def test_unretrieved_highlight_is_dropped():
    """
    LLM 不能凭空引用一个没有经过 search_highlights
    检索到的 Highlight。

    即使最终 JSON 格式完全合法，
    未检索到的 Highlight 也不能进入最终 Finding。
    """

    model = ScriptedModel(
        responses=[
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-search",
                        "type": "function",
                        "function": {
                            "name": "search_highlights",
                            "arguments": json.dumps(
                                {
                                    "top_k": 5,
                                }
                            ),
                        },
                    }
                ],
            },

            # 模型伪造一个不存在于检索结果中的 Highlight。
            {
                "content": json.dumps(
                    {
                        "answer": "发现一个可疑片段。",
                        "findings": [
                            {
                                "highlight_id": "fake-highlight",
                                "observation": (
                                    "该时间段出现大量"
                                    "笑声相关弹幕。"
                                ),
                                "interpretation": (
                                    "该片段可能引发了"
                                    "观众集中互动。"
                                ),
                                "confidence": 0.9,
                                "danmaku_ids": [
                                    101,
                                ],
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            },
        ]
    )

    tools = FakeEventScoutTools()

    scout = EventScout(
        model=model,
        tools=tools,
    )

    result = scout.run(
        query="有没有值得关注的片段？",
        vtuber_id="aza",
    )

    # fake-highlight 从未出现在 search_highlights 返回结果中，
    # 因此不能进入最终 Finding。
    assert result.findings == []

    assert [
        name
        for name, _
        in tools.calls
    ] == [
        "search_highlights",
    ]
    
def test_fake_danmaku_ids_are_replaced_with_real_evidence():
    """
    如果 LLM 引用了不存在的 danmaku_id，
    Runtime 不应直接接受伪造引用。

    当前策略：
    当模型给出的 danmaku_ids 全部无效时，
    Runtime 会 fallback 到实际检索结果中的前几条弹幕。

    因此最终 EvidenceRef 必须仍然指向真实 Evidence。
    """

    model = ScriptedModel(
        responses=[
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-search",
                        "type": "function",
                        "function": {
                            "name": "search_highlights",
                            "arguments": json.dumps(
                                {
                                    "top_k": 5,
                                }
                            ),
                        },
                    }
                ],
            },
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-danmaku",
                        "type": "function",
                        "function": {
                            "name": "get_danmaku_window",
                            "arguments": json.dumps(
                                {
                                    "highlight_id": "highlight-1",
                                }
                            ),
                        },
                    }
                ],
            },
            {
                "content": json.dumps(
                    {
                        "answer": "发现一个观众反应明显的片段。",
                        "findings": [
                            {
                                "highlight_id": "highlight-1",
                                "observation": (
                                    "该时间段出现大量"
                                    "笑声相关弹幕。"
                                ),
                                "interpretation": (
                                    "该片段可能引发了"
                                    "观众集中互动。"
                                ),
                                "confidence": 0.9,

                                # 故意伪造不存在的弹幕 ID。
                                "danmaku_ids": [
                                    999999,
                                ],
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            },
        ]
    )

    tools = FakeEventScoutTools()

    scout = EventScout(
        model=model,
        tools=tools,
    )

    result = scout.run(
        query="有没有观众反应明显的片段？",
        vtuber_id="aza",
    )

    assert len(result.findings) == 1

    finding = result.findings[0]

    # 伪造的 999999 不能进入最终 Evidence。
    assert "danmaku:999999" not in [
        evidence.id
        for evidence in finding.evidence
    ]

    # Runtime fallback 到真实检索到的弹幕。
    assert [
        evidence.id
        for evidence in finding.evidence
    ] == [
        "highlight:highlight-1",
        "danmaku:101",
        "danmaku:102",
    ]

def test_invalid_danmaku_ids_are_filtered_when_some_are_valid():
    """
    如果 LLM 同时引用真实和伪造的 danmaku_id，
    Runtime 只保留真实存在的引用。

    只要至少存在一个有效 ID，
    就不应该触发 fallback。
    """

    model = ScriptedModel(
        responses=[
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-search",
                        "type": "function",
                        "function": {
                            "name": "search_highlights",
                            "arguments": json.dumps(
                                {
                                    "top_k": 5,
                                }
                            ),
                        },
                    }
                ],
            },
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-danmaku",
                        "type": "function",
                        "function": {
                            "name": "get_danmaku_window",
                            "arguments": json.dumps(
                                {
                                    "highlight_id": "highlight-1",
                                }
                            ),
                        },
                    }
                ],
            },
            {
                "content": json.dumps(
                    {
                        "answer": "发现一个观众反应明显的片段。",
                        "findings": [
                            {
                                "highlight_id": "highlight-1",
                                "observation": (
                                    "该时间段出现大量"
                                    "笑声相关弹幕。"
                                ),
                                "interpretation": (
                                    "该片段可能引发了"
                                    "观众集中互动。"
                                ),
                                "confidence": 0.9,
                                "danmaku_ids": [
                                    101,
                                    999999,
                                ],
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            },
        ]
    )

    tools = FakeEventScoutTools()

    scout = EventScout(
        model=model,
        tools=tools,
    )

    result = scout.run(
        query="有没有观众反应明显的片段？",
        vtuber_id="aza",
    )

    assert len(result.findings) == 1

    finding = result.findings[0]

    assert [
        evidence.id
        for evidence in finding.evidence
    ] == [
        "highlight:highlight-1",
        "danmaku:101",
    ]

def test_invalid_final_json_raises_event_scout_error():
    """
    LLM 最终输出必须是合法 JSON。

    如果模型返回普通文本或损坏的 JSON，
    Runtime 应明确抛出 EventScoutError，
    而不是继续生成不可靠结果。
    """

    model = ScriptedModel(
        responses=[
            {
                "content": "这不是合法 JSON",
            }
        ]
    )

    tools = FakeEventScoutTools()

    scout = EventScout(
        model=model,
        tools=tools,
    )

    with pytest.raises(
        EventScoutError,
        match="not valid structured JSON",
    ):
        scout.run(
            query="最近有什么高光？",
            vtuber_id="aza",
        )

def test_missing_required_finding_field_raises_event_scout_error():
    """
    最终输出即使是合法 JSON，
    只要不符合 EventScoutDraft Schema，
    Runtime 也必须拒绝。
    """

    model = ScriptedModel(
        responses=[
            {
                "content": json.dumps(
                    {
                        "answer": "发现一个片段。",
                        "findings": [
                            {
                                "highlight_id": "highlight-1",

                                # 故意缺少 observation

                                "interpretation": (
                                    "该片段可能引发了"
                                    "观众集中互动。"
                                ),
                                "confidence": 0.9,
                                "danmaku_ids": [
                                    101,
                                ],
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            }
        ]
    )

    tools = FakeEventScoutTools()

    scout = EventScout(
        model=model,
        tools=tools,
    )

    with pytest.raises(
        EventScoutError,
        match="not valid structured JSON",
    ):
        scout.run(
            query="最近有什么高光？",
            vtuber_id="aza",
        )
        
        
def test_confidence_out_of_range_raises_event_scout_error():
    """
    confidence 必须位于 [0, 1]。

    如果 LLM 输出越界值，
    EventScoutDraft 的 Pydantic 校验应失败，
    Runtime 必须拒绝该结果。
    """

    model = ScriptedModel(
        responses=[
            {
                "content": json.dumps(
                    {
                        "answer": "发现一个片段。",
                        "findings": [
                            {
                                "highlight_id": "highlight-1",
                                "observation": (
                                    "该时间段出现大量"
                                    "笑声相关弹幕。"
                                ),
                                "interpretation": (
                                    "该片段可能引发了"
                                    "观众集中互动。"
                                ),

                                # 故意越界
                                "confidence": 1.5,

                                "danmaku_ids": [
                                    101,
                                ],
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            }
        ]
    )

    tools = FakeEventScoutTools()

    scout = EventScout(
        model=model,
        tools=tools,
    )

    with pytest.raises(
        EventScoutError,
        match="not valid structured JSON",
    ):
        scout.run(
            query="最近有什么高光？",
            vtuber_id="aza",
        )

def test_get_danmaku_before_search_highlights_is_rejected():
    """
    Event Scout 必须先通过 search_highlights 获取候选，
    才能调用 get_danmaku_window 获取对应证据。

    即使最终两类数据都被取到了，
    也不能接受逆序调用。
    """

    model = ScriptedModel(
        responses=[
            # 错误：先取弹幕
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-danmaku",
                        "type": "function",
                        "function": {
                            "name": "get_danmaku_window",
                            "arguments": json.dumps(
                                {
                                    "highlight_id": "highlight-1",
                                }
                            ),
                        },
                    }
                ],
            },

            # 后补 search_highlights
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-search",
                        "type": "function",
                        "function": {
                            "name": "search_highlights",
                            "arguments": json.dumps(
                                {
                                    "top_k": 5,
                                }
                            ),
                        },
                    }
                ],
            },

            {
                "content": json.dumps(
                    {
                        "answer": "发现一个片段。",
                        "findings": [
                            {
                                "highlight_id": "highlight-1",
                                "observation": (
                                    "该时间段出现大量"
                                    "笑声相关弹幕。"
                                ),
                                "interpretation": (
                                    "该片段可能引发了"
                                    "观众集中互动。"
                                ),
                                "confidence": 0.9,
                                "danmaku_ids": [
                                    101,
                                ],
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            },
        ]
    )

    tools = FakeEventScoutTools()

    scout = EventScout(
        model=model,
        tools=tools,
    )

    with pytest.raises(
        EventScoutError,
        match="search_highlights",
    ):
        scout.run(
            query="最近有什么高光？",
            vtuber_id="aza",
        )

def test_malformed_tool_arguments_do_not_reuse_previous_arguments():
    """
    如果某次 Tool Call 的 arguments 无法解析，
    Trace 中不能复用上一次成功 Tool Call 的 arguments。

    失败调用应该记录空参数，而不是 stale arguments。
    """

    model = ScriptedModel(
        responses=[
            # 第一次调用：合法
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-search",
                        "type": "function",
                        "function": {
                            "name": "search_highlights",
                            "arguments": json.dumps(
                                {
                                    "top_k": 5,
                                }
                            ),
                        },
                    }
                ],
            },

            # 第二次调用：故意给损坏 JSON
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-broken",
                        "type": "function",
                        "function": {
                            "name": "get_danmaku_window",
                            "arguments": "{broken-json",
                        },
                    }
                ],
            },

            # 最后正常结束
            {
                "content": json.dumps(
                    {
                        "answer": "没有足够证据形成 Finding。",
                        "findings": [],
                    },
                    ensure_ascii=False,
                )
            },
        ]
    )

    tools = FakeEventScoutTools()

    scout = EventScout(
        model=model,
        tools=tools,
    )

    result = scout.run(
        query="最近有什么高光？",
        vtuber_id="aza",
    )

    tool_steps = [
        step
        for step in result.trace
        if step.action == "tool"
    ]

    assert len(tool_steps) == 2

    assert tool_steps[0].arguments == {
        "top_k": 5,
    }

    # 损坏 JSON 不能沿用上一轮 {"top_k": 5}
    assert tool_steps[1].arguments == {}
    
def test_tool_call_budget_exceeded_raises_event_scout_error():
    """
    Agent 的 Tool Call 数量不能超过 max_tool_calls。

    超过预算后 Runtime 必须立即停止，
    防止模型陷入无休止 Tool Calling。
    """

    model = ScriptedModel(
        responses=[
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-search-1",
                        "type": "function",
                        "function": {
                            "name": "search_highlights",
                            "arguments": json.dumps(
                                {
                                    "top_k": 5,
                                }
                            ),
                        },
                    },
                    {
                        "id": "call-search-2",
                        "type": "function",
                        "function": {
                            "name": "search_highlights",
                            "arguments": json.dumps(
                                {
                                    "top_k": 3,
                                }
                            ),
                        },
                    },
                ],
            }
        ]
    )

    tools = FakeEventScoutTools()

    scout = EventScout(
        model=model,
        tools=tools,
        max_tool_calls=1,
    )

    with pytest.raises(
        EventScoutError,
        match="exceeded tool call budget",
    ):
        scout.run(
            query="最近有什么高光？",
            vtuber_id="aza",
        )

    # 第一条 Tool Call 已执行，
    # 第二条在执行前就因为预算超限被拒绝。
    assert len(tools.calls) == 1

    assert tools.calls[0][0] == "search_highlights"
    
def test_empty_query_raises_value_error():
    """
    空查询不应该进入 Agent Runtime。

    EventScout.run() 应在调用模型前直接拒绝。
    """

    model = ScriptedModel(
        responses=[]
    )

    tools = FakeEventScoutTools()

    scout = EventScout(
        model=model,
        tools=tools,
    )

    with pytest.raises(
        ValueError,
        match="query cannot be empty",
    ):
        scout.run(
            query="   ",
            vtuber_id="aza",
        )

    # 不应调用任何 Tool
    assert tools.calls == []

    # 也不应调用模型
    assert model.call_count == 0
