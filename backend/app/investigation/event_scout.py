import json
from typing import (
    Any,
)

from pydantic import (
    ValidationError,
)

from app.investigation.model_client import (
    OpenAICompatibleChatClient,
)
from app.investigation.models import (
    EvidenceRef,
    EventScoutDraft,
    EventScoutFinding,
    EventScoutResult,
    EventScoutTraceStep,
)
from app.investigation.tools import (
    EventScoutTools,
)

from app.agent.prompts.loader import load_prompt


class EventScoutError(
    RuntimeError
):
    pass


class EventScout:
    def __init__(
        self,
        *,
        model: (
            OpenAICompatibleChatClient
        ),
        tools: EventScoutTools,
        max_steps: int = 6,
        max_tool_calls: int = 12,
    ) -> None:
        self.model = model
        self.tools = tools

        self.max_steps = (
            max_steps
        )

        self.max_tool_calls = (
            max_tool_calls
        )

    def run(
        self,
        *,
        query: str,
        vtuber_id: str,
    ) -> EventScoutResult:
        query = query.strip()

        if not query:
            raise ValueError(
                "query cannot be empty"
            )

        messages: list[
            dict[str, Any]
        ] = [
            {
                "role": "system",
                "content": load_prompt("event_scout"),
            },
            {
                "role": "user",
                "content": (
                    "当前 VTuber workspace: "
                    f"{vtuber_id}\n\n"
                    "用户问题："
                    f"{query}"
                ),
            },
        ]

        trace: list[
            EventScoutTraceStep
        ] = []

        retrieved_highlights: dict[
            str,
            dict,
        ] = {}

        retrieved_danmaku: dict[
            str,
            list[dict],
        ] = {}

        total_tool_calls = 0

        for step in range(
            1,
            self.max_steps + 1,
        ):
            trace.append(
                EventScoutTraceStep(
                    step=step,
                    action="model",
                )
            )

            message = (
                self.model.complete(
                    messages=messages,
                    tools=(
                        self.tools
                        .tool_schemas()
                    ),
                )
            )

            tool_calls = (
                message.get(
                    "tool_calls"
                )
                or []
            )

            if tool_calls:
                assistant_message = {
                    "role": "assistant",
                    "content": (
                        message.get(
                            "content"
                        )
                        or ""
                    ),
                    "tool_calls": (
                        tool_calls
                    ),
                }

                messages.append(
                    assistant_message
                )

                for tool_call in tool_calls:
                    total_tool_calls += 1

                    if (
                        total_tool_calls
                        > self.max_tool_calls
                    ):
                        raise EventScoutError(
                            "Event Scout exceeded "
                            "tool call budget"
                        )

                    tool_call_id = str(
                        tool_call.get(
                            "id",
                            "",
                        )
                    )

                    function = (
                        tool_call.get(
                            "function"
                        )
                        or {}
                    )

                    tool_name = str(
                        function.get(
                            "name",
                            "",
                        )
                    )

                    raw_arguments = (
                        function.get(
                            "arguments"
                        )
                        or "{}"
                    )

                    try:
                        arguments = (
                            json.loads(
                                raw_arguments
                            )
                            if isinstance(
                                raw_arguments,
                                str,
                            )
                            else dict(
                                raw_arguments
                            )
                        )

                        result = (
                            self.tools.execute(
                                tool_name,
                                arguments,
                            )
                        )

                    except Exception as exc:
                        result = {
                            "error": str(
                                exc
                            )
                        }

                    trace.append(
                        EventScoutTraceStep(
                            step=step,
                            action="tool",
                            tool_name=(
                                tool_name
                            ),
                            arguments=(
                                arguments
                                if (
                                    "arguments"
                                    in locals()
                                )
                                else {}
                            ),
                        )
                    )

                    self._remember_tool_result(
                        tool_name=tool_name,
                        result=result,
                        retrieved_highlights=(
                            retrieved_highlights
                        ),
                        retrieved_danmaku=(
                            retrieved_danmaku
                        ),
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": (
                                tool_call_id
                            ),
                            "content": (
                                json.dumps(
                                    result,
                                    ensure_ascii=False,
                                )
                            ),
                        }
                    )

                continue

            content = str(
                message.get(
                    "content",
                    "",
                )
            ).strip()
            
            print("===== RAW KIMI CONTENT =====")
            print(content[:500])
            print("============================")

            draft = (
                self._parse_final(
                    content
                )
            )

            findings = (
                self._hydrate_findings(
                    draft=draft,
                    retrieved_highlights=(
                        retrieved_highlights
                    ),
                    retrieved_danmaku=(
                        retrieved_danmaku
                    ),
                )
            )

            trace.append(
                EventScoutTraceStep(
                    step=step,
                    action="final",
                )
            )

            return EventScoutResult(
                query=query,
                vtuber_id=vtuber_id,
                answer=(
                    draft.answer
                ),
                findings=findings,
                trace=trace,
            )

        raise EventScoutError(
            "Event Scout exceeded "
            "maximum reasoning steps"
        )

    @staticmethod
    def _remember_tool_result(
        *,
        tool_name: str,
        result: dict,
        retrieved_highlights: dict[
            str,
            dict,
        ],
        retrieved_danmaku: dict[
            str,
            list[dict],
        ],
    ) -> None:
        if (
            tool_name
            == "search_highlights"
        ):
            for candidate in (
                result.get(
                    "candidates",
                    []
                )
            ):
                highlight_id = (
                    candidate.get(
                        "highlight_id"
                    )
                )

                if highlight_id:
                    retrieved_highlights[
                        str(
                            highlight_id
                        )
                    ] = candidate

        elif (
            tool_name
            == "get_danmaku_window"
        ):
            highlight_id = (
                result.get(
                    "highlight_id"
                )
            )

            if highlight_id:
                retrieved_danmaku[
                    str(
                        highlight_id
                    )
                ] = list(
                    result.get(
                        "danmaku",
                        []
                    )
                )

    @staticmethod
    def _parse_final(
        content: str,
    ) -> EventScoutDraft:
        cleaned = (
            content.strip()
        )

        if cleaned.startswith(
            "```"
        ):
            lines = (
                cleaned.splitlines()
            )

            if lines:
                lines = lines[1:]

            if (
                lines
                and lines[-1]
                .strip()
                == "```"
            ):
                lines = lines[:-1]

            cleaned = (
                "\n".join(
                    lines
                ).strip()
            )

        try:
            payload = (
                json.loads(
                    cleaned
                )
            )

            return (
                EventScoutDraft
                .model_validate(
                    payload
                )
            )

        except (
            json.JSONDecodeError,
            ValidationError,
        ) as exc:
            raise EventScoutError(
                "Event Scout final response "
                "is not valid structured JSON"
            ) from exc

    @staticmethod
    def _hydrate_findings(
        *,
        draft: EventScoutDraft,
        retrieved_highlights: dict[
            str,
            dict,
        ],
        retrieved_danmaku: dict[
            str,
            list[dict],
        ],
    ) -> list[
        EventScoutFinding
    ]:
        findings: list[
            EventScoutFinding
        ] = []

        for item in (
            draft.findings[:5]
        ):
            candidate = (
                retrieved_highlights
                .get(
                    item.highlight_id
                )
            )

            evidence_items = (
                retrieved_danmaku
                .get(
                    item.highlight_id
                )
            )

            # 只有真正经过：
            #
            # search_highlights
            # +
            # get_danmaku_window
            #
            # 的候选才能进入最终 Finding。
            if (
                candidate is None
                or evidence_items is None
            ):
                continue

            by_id = {
                int(
                    evidence[
                        "id"
                    ]
                ): evidence
                for evidence
                in evidence_items
            }

            allowed_ids = [
                danmaku_id
                for danmaku_id
                in item.danmaku_ids
                if (
                    danmaku_id
                    in by_id
                )
            ]

            if not allowed_ids:
                allowed_ids = list(
                    by_id.keys()
                )[:3]

            evidence_refs = [
                EvidenceRef(
                    kind="highlight",
                    id=(
                        "highlight:"
                        f"{item.highlight_id}"
                    ),
                )
            ]

            evidence_refs.extend(
                EvidenceRef(
                    kind="danmaku",
                    id=(
                        "danmaku:"
                        f"{danmaku_id}"
                    ),
                )
                for danmaku_id
                in allowed_ids[:8]
            )

            findings.append(
                EventScoutFinding(
                    highlight_id=(
                        item.highlight_id
                    ),
                    stream_id=(
                        candidate[
                            "stream_id"
                        ]
                    ),
                    stream_title=(
                        candidate[
                            "stream_title"
                        ]
                    ),
                    live_time=str(
                        candidate[
                            "live_time"
                        ]
                    ),
                    part_id=(
                        candidate[
                            "part_id"
                        ]
                    ),
                    start_ms=int(
                        candidate[
                            "start_ms"
                        ]
                    ),
                    end_ms=int(
                        candidate[
                            "end_ms"
                        ]
                    ),
                    peak_ms=int(
                        candidate[
                            "peak_ms"
                        ]
                    ),
                    score=float(
                        candidate[
                            "score"
                        ]
                    ),
                    audience_summary=(
                        item
                        .audience_summary
                    ),
                    confidence=(
                        item.confidence
                    ),
                    evidence=(
                        evidence_refs
                    ),
                )
            )

        return findings