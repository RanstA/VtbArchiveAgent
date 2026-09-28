import json

from pydantic import BaseModel, Field

from app.event_pipeline.events import (
    EventCandidate,
)
from pydantic import ValidationError

from app.agent.prompts.loader import load_prompt
from app.domain.event import (
    Event,
    make_event_id,
)
from app.investigation.model_client import (
    OpenAICompatibleChatClient,
)

SEMANTICIZER_VERSION = "v1"


class EventSemanticizerInput(BaseModel):
    """
    Event Semanticizer 的输入。
    EventCandidate 提供事件结构边界，
    danmaku_texts 提供当前可用的观众反应证据。
    """

    candidate: EventCandidate

    stream_title: str = Field(min_length=1)

    danmaku_texts: list[str] = Field(min_length=1)


class EventSemanticizerDraft(BaseModel):
    """
    LLM 对 EventCandidate 生成的语义草稿。
    这里只保存模型负责生成的字段。
    """

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)


def build_semantic_text(
    draft: EventSemanticizerDraft,
) -> str:
    """
    为 BM25 / Vector Retrieval 确定性构造统一检索文本。
    """

    parts = [
        draft.title.strip(),
        draft.summary.strip(),
        *(item.strip() for item in draft.keywords if item.strip()),
        *(item.strip() for item in draft.entities if item.strip()),
    ]

    return "\n".join(parts)


def build_user_message(
    semanticizer_input: EventSemanticizerInput,
) -> str:
    """
    将结构化输入转换成提供给模型的 JSON。
    """

    payload = {
        "streamTitle": (semanticizer_input.stream_title),
        "event": {
            "streamId": semanticizer_input.candidate.stream_id,
            "partId": semanticizer_input.candidate.part_id,
            "startMs": semanticizer_input.candidate.start_ms,
            "endMs": semanticizer_input.candidate.end_ms,
            "peakMs": semanticizer_input.candidate.peak_ms,
        },
        "danmaku": semanticizer_input.danmaku_texts,
    }

    return json.dumps(payload, ensure_ascii=False, indent=2)


class EventSemanticizerError(RuntimeError):
    pass

class EventSemanticizer:
    def __init__(
        self,
        *,
        model: OpenAICompatibleChatClient,
        semanticizer_version: str = SEMANTICIZER_VERSION,
    ) -> None:
        semanticizer_version = (
            semanticizer_version.strip()
        )

        if not semanticizer_version:
            raise ValueError(
                "semanticizer_version cannot be empty"
            )

        self.model = model
        self.semanticizer_version = (
            semanticizer_version
        )

    def semanticize(
        self,
        semanticizer_input: EventSemanticizerInput,
    ) -> Event:
        messages = [
            {
                "role": "system",
                "content": load_prompt(
                    "event_semanticizer"
                ),
            },
            {
                "role": "user",
                "content": build_user_message(
                    semanticizer_input
                ),
            },
        ]

        message = self.model.complete(
            messages=messages
        )

        content = str(
            message.get(
                "content",
                "",
            )
        ).strip()

        draft = self._parse_draft(
            content
        )

        candidate = (
            semanticizer_input.candidate
        )

        semantic_text = (
            build_semantic_text(
                draft
            )
        )

        return Event(
            id=make_event_id(
                stream_id=(
                    candidate.stream_id
                ),
                part_id=(
                    candidate.part_id
                ),
                source_highlight_ids=(
                    candidate
                    .source_highlight_ids
                ),
            ),
            stream_id=(
                candidate.stream_id
            ),
            part_id=(
                candidate.part_id
            ),
            start_ms=(
                candidate.start_ms
            ),
            end_ms=(
                candidate.end_ms
            ),
            peak_ms=(
                candidate.peak_ms
            ),
            source_highlight_ids=(
                candidate
                .source_highlight_ids
            ),
            title=draft.title.strip(),
            summary=draft.summary.strip(),
            keywords=[
                item.strip()
                for item in draft.keywords
                if item.strip()
            ],
            entities=[
                item.strip()
                for item in draft.entities
                if item.strip()
            ],
            semantic_text=(
                semantic_text
            ),
            semanticizer_version=(
                self.semanticizer_version
            ),
        )

    @staticmethod
    def _parse_draft(
        content: str,
    ) -> EventSemanticizerDraft:
        cleaned = content.strip()

        if cleaned.startswith("```"):
            lines = cleaned.splitlines()

            if lines:
                lines = lines[1:]

            if (
                lines
                and lines[-1].strip()
                == "```"
            ):
                lines = lines[:-1]

            cleaned = "\n".join(
                lines
            ).strip()

        try:
            payload = json.loads(
                cleaned
            )

            return (
                EventSemanticizerDraft
                .model_validate(
                    payload
                )
            )

        except (
            json.JSONDecodeError,
            ValidationError,
        ) as exc:
            raise EventSemanticizerError(
                "Event Semanticizer response "
                "is not valid structured JSON"
            ) from exc

