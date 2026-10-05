import json
import sqlite3

from pydantic import ValidationError

from app.agent.prompts.loader import load_prompt
from app.investigation.model_client import (
    OpenAICompatibleChatClient,
)
from app.pipeline.topic_analysis import (
    TopicAnalysisResult,
    validate_topic_analysis,
    validate_topic_analysis_evidence,
    normalize_topic_analysis_evidence
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

        messages = [
            {
                "role": "system",
                "content": load_prompt(
                    "topic_analyzer"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请分析以下 TopicCandidate：\n\n"
                    + context
                ),
            },
        ]

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