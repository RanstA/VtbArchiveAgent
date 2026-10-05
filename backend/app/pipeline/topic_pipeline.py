import sqlite3
import time
from app.domain.pipeline.topic_segment import (
    TopicSegment,
)
from app.pipeline.topic_analyzer import (
    TopicAnalyzer,
)
from app.pipeline.topic_candidate import (
    build_topic_candidates,
)
from app.pipeline.topic_segment_builder import (
    build_topic_segments,
)
from app.repository.reaction_match_repo import (
    list_reaction_matches_by_stream,
)


class TopicPipelineError(RuntimeError):
    pass


def _validate_candidate_coverage(
    *,
    expected_reaction_match_ids: list[str],
    candidate_reaction_match_ids: list[str],
) -> None:
    if len(candidate_reaction_match_ids) != len(set(candidate_reaction_match_ids)):
        raise TopicPipelineError(
            "topic candidates contain duplicate " "reaction matches"
        )

    if candidate_reaction_match_ids != (expected_reaction_match_ids):
        raise TopicPipelineError(
            "topic candidates do not preserve "
            "complete reaction match coverage "
            "and order"
        )


def _validate_segment_coverage(
    *,
    expected_reaction_match_ids: list[str],
    topic_segments: list[TopicSegment],
) -> None:
    actual_reaction_match_ids = [
        reaction_match_id
        for segment in topic_segments
        for reaction_match_id in (segment.reaction_match_ids)
    ]

    if len(actual_reaction_match_ids) != len(set(actual_reaction_match_ids)):
        raise TopicPipelineError("topic segments contain duplicate " "reaction matches")

    if actual_reaction_match_ids != (expected_reaction_match_ids):
        raise TopicPipelineError(
            "topic segments do not preserve "
            "complete reaction match coverage "
            "and order"
        )


def build_topic_segments_for_stream(
    connection: sqlite3.Connection,
    *,
    stream_id: str,
    analyzer: TopicAnalyzer,
) -> list[TopicSegment]:
    reaction_matches = list_reaction_matches_by_stream(
        connection,
        stream_id=stream_id,
    )

    expected_reaction_match_ids = [
        reaction_match.id for reaction_match in reaction_matches
    ]

    candidates = build_topic_candidates(
        connection,
        stream_id=stream_id,
    )

    candidate_reaction_match_ids = [
        reaction_match_id
        for candidate in candidates
        for reaction_match_id in (candidate.reaction_match_ids)
    ]

    _validate_candidate_coverage(
        expected_reaction_match_ids=(expected_reaction_match_ids),
        candidate_reaction_match_ids=(candidate_reaction_match_ids),
    )

    topic_segments: list[TopicSegment] = []

    for candidate_index, candidate in enumerate(
        candidates,
        start=1,
    ):
        try:
            print(
                f"Analyzing candidate "
                f"{candidate_index}/{len(candidates)}..."
            )

            analysis = analyzer.analyze(
                connection,
                candidate=candidate,
            )

            segments = build_topic_segments(
                connection,
                candidate=candidate,
                analysis=analysis,
            )

        except Exception as exc:
            raise TopicPipelineError(
                "topic pipeline failed at "
                f"candidate #{candidate_index}"
            ) from exc

        topic_segments.extend(
            segments
        )

        if candidate_index < len(candidates):
            time.sleep(21)
            
    _validate_segment_coverage(
        expected_reaction_match_ids=(expected_reaction_match_ids),
        topic_segments=topic_segments,
    )

    return topic_segments
