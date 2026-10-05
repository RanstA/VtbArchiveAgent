import sqlite3

from app.domain.pipeline.topic_segment import (
    TopicSegment,
)
from app.pipeline.topic_analysis import (
    TopicAnalysisResult,
)
from app.pipeline.topic_candidate import (
    TopicCandidate,
)
from app.repository.highlight_repo import (
    get_highlight_by_id,
)
from app.repository.reaction_match_repo import (
    get_reaction_match_by_id,
)
from app.repository.stream_part_repo import (
    list_stream_parts,
)


TOPIC_ANALYZER_VERSION = "topic-analyzer-v0"


def build_topic_segments(
    connection: sqlite3.Connection,
    *,
    candidate: TopicCandidate,
    analysis: TopicAnalysisResult,
) -> list[TopicSegment]:
    parts = list_stream_parts(
        connection,
        candidate.stream_id,
    )

    part_offsets = {
        part["part_id"]: part["start_offset_ms"]
        for part in parts
    }

    segments: list[TopicSegment] = []

    for topic in analysis.topics:
        reaction_matches = []
        highlights = []

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

            highlight = get_highlight_by_id(
                connection,
                reaction_match.highlight_id,
            )

            if highlight is None:
                raise ValueError(
                    "highlight does not exist: "
                    f"{reaction_match.highlight_id}"
                )

            reaction_matches.append(
                reaction_match
            )

            highlights.append(
                highlight
            )

        source_part_ids: list[str] = []

        global_windows: list[
            tuple[int, int]
        ] = []

        for reaction_match, highlight in zip(
            reaction_matches,
            highlights,
        ):
            if reaction_match.part_id not in part_offsets:
                raise ValueError(
                    "missing StreamPart offset: "
                    f"{reaction_match.part_id}"
                )

            if reaction_match.part_id not in source_part_ids:
                source_part_ids.append(
                    reaction_match.part_id
                )

            offset_ms = part_offsets[
                reaction_match.part_id
            ]

            global_windows.append(
                (
                    offset_ms + highlight.start_ms,
                    offset_ms + highlight.end_ms,
                )
            )

        start_ms = min(
            start
            for start, _ in global_windows
        )

        end_ms = max(
            end
            for _, end in global_windows
        )

        salience_score = max(
            highlight.score
            for highlight in highlights
        )

        segments.append(
            TopicSegment(
                stream_id=candidate.stream_id,
                source_part_ids=source_part_ids,
                reaction_match_ids=topic.reaction_match_ids,
                start_ms=start_ms,
                end_ms=end_ms,
                title=topic.title,
                summary=topic.summary,
                keywords=topic.keywords,
                entities=topic.entities,
                transcript_segment_ids=(
                    topic.transcript_segment_ids
                ),
                salience_score=salience_score,
                confidence=topic.confidence,
                topic_type=topic.topic_type,
                analyzer_version=(
                    TOPIC_ANALYZER_VERSION
                ),
            )
        )

    return segments