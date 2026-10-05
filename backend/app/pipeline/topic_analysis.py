import sqlite3
from typing import Literal
from app.repository.reaction_match_repo import get_reaction_match_by_id
from pydantic import BaseModel, Field
from app.pipeline.topic_candidate import TopicCandidate

TopicType = Literal[
    "talk",
    "interaction",
    "singing",
    "gameplay",
    "reaction",
    "announcement",
]

class AnalyzedTopic(BaseModel):
    reaction_match_ids: list[str] = Field(
        min_length=1, description=("属于当前话题的连续 ReactionMatch ID 列表")
    )

    transcript_segment_ids: list[str] = Field(
        min_length=1,
        description="直接支撑当前话题语义的 TranscriptSegment ID 列表",
    )
    
    topic_type: TopicType = Field(
        description="当前话题的一级内容分类",
    )

    title: str = Field(
        min_length=1,
        description="话题的简短标题",
    )

    summary: str = Field(min_length=1, description="对该话题主要内容的简要总结")

    keywords: list[str] = Field(description="用于检索和话题识别的关键词")

    entities: list[str] = Field(description=("话题涉及的人物、作品、地点等实体"))

    confidence: float = Field(
        ge=0.0, le=1.0, description=("对该话题划分和语义理解的置信度")
    )


class TopicAnalysisResult(BaseModel):
    topics: list[AnalyzedTopic] = Field(
        min_length=1, description=("当前 TopicCandidate " "经过语义分析得到的话题列表")
    )


def validate_topic_analysis(
    candidate: TopicCandidate,
    result: TopicAnalysisResult,
) -> None:
    expected_ids = candidate.reaction_match_ids

    actual_ids = [
        reaction_match_id
        for topic in result.topics
        for reaction_match_id in topic.reaction_match_ids
    ]

    if len(actual_ids) != len(set(actual_ids)):
        raise ValueError("topic analysis contains " "duplicate reaction_match_ids")

    expected_set = set(expected_ids)
    actual_set = set(actual_ids)

    missing_ids = expected_set - actual_set

    unexpected_ids = actual_set - expected_set

    if missing_ids:
        raise ValueError(
            "topic analysis is missing " "reaction matches: " f"{sorted(missing_ids)}"
        )

    if unexpected_ids:
        raise ValueError(
            "topic analysis contains "
            "unexpected reaction matches: "
            f"{sorted(unexpected_ids)}"
        )

    if actual_ids != expected_ids:
        raise ValueError(
            "topic analysis must preserve "
            "candidate reaction match order "
            "and contiguous topic boundaries"
        )


def validate_topic_analysis_evidence(
    connection: sqlite3.Connection,
    *,
    result: TopicAnalysisResult,
) -> None:
    for topic in result.topics:
        allowed_transcript_ids: set[str] = set()

        for reaction_match_id in topic.reaction_match_ids:
            reaction_match = get_reaction_match_by_id(
                connection,
                reaction_match_id,
            )

            if reaction_match is None:
                raise ValueError(
                    "reaction match does not exist: "
                    f"{reaction_match_id}"
                )

            allowed_transcript_ids.update(
                reaction_match.transcript_segment_ids
            )

        actual_ids = topic.transcript_segment_ids

        if len(actual_ids) != len(set(actual_ids)):
            raise ValueError(
                "topic analysis contains duplicate "
                "transcript_segment_ids"
            )

        unexpected_ids = (
            set(actual_ids)
            - allowed_transcript_ids
        )

        if unexpected_ids:
            raise ValueError(
                "topic analysis contains transcript "
                "segments outside its reaction matches: "
                f"{sorted(unexpected_ids)}"
            )
            
            
            
def normalize_topic_analysis_evidence(
    result: TopicAnalysisResult,
) -> None:
    for topic in result.topics:
        topic.transcript_segment_ids = list(
            dict.fromkeys(
                topic.transcript_segment_ids
            )
        )