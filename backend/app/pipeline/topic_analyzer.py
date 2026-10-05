import json
import sqlite3

from pydantic import ValidationError

from app.agent.prompts.loader import load_prompt
from app.investigation.model_client import (
    OpenAICompatibleChatClient,
)
from app.pipeline.topic_analysis import (
    TopicAnalysisResult,
    normalize_topic_analysis_evidence,
    validate_topic_analysis,
    validate_topic_analysis_evidence,
)
from app.pipeline.topic_candidate import (
    TopicCandidate,
)
from app.pipeline.topic_context import (
    build_topic_candidate_context,
)


class TopicAnalyzerError(RuntimeError):
    pass


class TopicAnalyzer:
    def __init__(
        self,
        *,
        model: OpenAICompatibleChatClient,
    ) -> None:
        self.model = model

    def analyze(
        self,
        connection: sqlite3.Connection,
        *,
        candidate: TopicCandidate,
    ) -> TopicAnalysisResult:
        context = build_topic_candidate_context(
            connection,
            candidate=candidate,
        )

        system_prompt = load_prompt(
            "topic_analyzer"
        )

        user_prompt = (
            "请分析以下 TopicCandidate：\n\n"
            + context
        )

        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]

        first_content = self._complete(
            messages
        )

        try:
            return self._parse_and_validate(
                connection,
                candidate=candidate,
                content=first_content,
            )

        except (
            TopicAnalyzerError,
            ValueError,
        ) as first_error:
            repair_messages = [
                *messages,
                {
                    "role": "assistant",
                    "content": first_content,
                },
                {
                    "role": "user",
                    "content": (
                        "你上一次的输出没有通过系统校验。\n\n"
                        "校验错误：\n"
                        f"{first_error}\n\n"
                        "请重新检查 Topic 划分和 Evidence 引用，"
                        "特别确保：\n"
                        "1. 每个 reaction_match_id 必须且只能出现一次；\n"
                        "2. reaction_match_ids 必须保持原始顺序；\n"
                        "3. 每个 Topic 的 transcript_segment_ids "
                        "只能来自该 Topic 自己包含的 "
                        "reaction_match_ids；\n"
                        "4. 不得引用相邻 Topic 或其他 "
                        "ReactionMatch 的 Transcript；\n"
                        "5. 不得创建或猜测任何 ID；\n"
                        "6. 保持 topic_type 为允许的六种类型之一；\n"
                        "7. 只输出完整、合法的 JSON，"
                        "不要解释修改过程。"
                    ),
                },
            ]

            repaired_content = self._complete(
                repair_messages
            )

            try:
                return self._parse_and_validate(
                    connection,
                    candidate=candidate,
                    content=repaired_content,
                )

            except (
                TopicAnalyzerError,
                ValueError,
            ) as second_error:
                raise TopicAnalyzerError(
                    "topic analyzer output failed "
                    "validation after one repair retry: "
                    f"{second_error}"
                ) from second_error

    def _complete(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        message = self.model.complete(
            messages=messages,
        )

        content = str(
            message.get(
                "content",
                "",
            )
        ).strip()

        if not content:
            raise TopicAnalyzerError(
                "topic analyzer returned "
                "empty content"
            )

        return content

    def _parse_and_validate(
        self,
        connection: sqlite3.Connection,
        *,
        candidate: TopicCandidate,
        content: str,
    ) -> TopicAnalysisResult:
        result = self._parse_result(
            content
        )

        validate_topic_analysis(
            candidate,
            result,
        )

        normalize_topic_analysis_evidence(
            result
        )

        validate_topic_analysis_evidence(
            connection,
            result=result,
        )

        return result

    @staticmethod
    def _parse_result(
        content: str,
    ) -> TopicAnalysisResult:
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
                TopicAnalysisResult
                .model_validate(
                    payload
                )
            )

        except (
            json.JSONDecodeError,
            ValidationError,
        ) as exc:
            raise TopicAnalyzerError(
                "topic analyzer output "
                "is not valid structured JSON"
            ) from exc