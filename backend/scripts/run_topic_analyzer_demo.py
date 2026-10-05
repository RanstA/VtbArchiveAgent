from pathlib import Path

from app.config.settings import settings
from app.investigation.model_client import (
    OpenAICompatibleChatClient,
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
from app.repository.database import (
    connect_db,
    init_db,
)
from app.repository.topic_segment_repo import (
    list_topic_segments_by_stream,
    replace_topic_segments_for_stream,
)

DB_PATH = Path("aza_demo_v1.db")

STREAM_ID = "c05f34e0-b116-5671-8013-5d63f144ca70"

CANDIDATE_INDEX = 11


def main() -> None:
    if not settings.event_scout_api_base_url:
        raise RuntimeError("EVENT_SCOUT_API_BASE_URL is not configured")

    if not settings.event_scout_model:
        raise RuntimeError("EVENT_SCOUT_MODEL is not configured")

    model = OpenAICompatibleChatClient(
        base_url=settings.event_scout_api_base_url,
        api_key=settings.event_scout_api_key,
        model=settings.event_scout_model,
        timeout_seconds=settings.event_scout_timeout_seconds,
        extra_body={
            "temperature": 0.6,
            "thinking": {
                "type": "disabled",
            },
        },
    )
    analyzer = TopicAnalyzer(
        model=model,
    )

    connection = connect_db(DB_PATH)
    init_db(connection)

    try:
        candidates = build_topic_candidates(
            connection,
            stream_id=STREAM_ID,
        )

        candidate = candidates[CANDIDATE_INDEX]

        print(
            "Candidate:",
            CANDIDATE_INDEX + 1,
        )

        print(
            "ReactionMatches:",
            len(candidate.reaction_match_ids),
        )

        print()

        result = analyzer.analyze(
            connection,
            candidate=candidate,
        )
        segments = build_topic_segments(
            connection,
            candidate=candidate,
            analysis=result,
        )

        replace_topic_segments_for_stream(
            connection,
            stream_id=STREAM_ID,
            topic_segments=segments,
        )

        persisted_segments = list_topic_segments_by_stream(
            connection,
            stream_id=STREAM_ID,
        )

        assert len(persisted_segments) == len(segments)

        assert [segment.model_dump() for segment in persisted_segments] == [
            segment.model_dump() for segment in segments
        ]

        print()
        print("=== PERSISTENCE CHECK ===")
        print(
            "built:",
            len(segments),
        )
        print(
            "persisted:",
            len(persisted_segments),
        )
        print(
            "round trip: OK",
        )

        print()

        for index, segment in enumerate(
            persisted_segments,
            start=1,
        ):
            print(
                f"{index}. "
                f"{segment.start_ms} -> "
                f"{segment.end_ms} | "
                f"{segment.title}"
            )

        segments = build_topic_segments(
            connection,
            candidate=candidate,
            analysis=result,
        )

        print()
        print("=== TOPIC SEGMENTS ===")
        print()

        for index, segment in enumerate(
            segments,
            start=1,
        ):
            print(f"=== SEGMENT #{index} ===")

            print(
                "id:",
                segment.id,
            )

            print(
                "parts:",
                segment.source_part_ids,
            )

            print(
                "reaction matches:",
                segment.reaction_match_ids,
            )

            print(
                "range:",
                segment.start_ms,
                "->",
                segment.end_ms,
            )

            print(
                "salience:",
                segment.salience_score,
            )

            print(
                "confidence:",
                segment.confidence,
            )

            print(
                "title:",
                segment.title,
            )

            print(
                "transcripts:",
                len(segment.transcript_segment_ids),
            )

            print()

        for index, topic in enumerate(
            result.topics,
            start=1,
        ):
            print(f"=== TOPIC #{index} ===")

            print(
                "title:",
                topic.title,
            )

            print(
                "reaction matches:",
                topic.reaction_match_ids,
            )

            print(
                "transcripts:",
                len(topic.transcript_segment_ids),
            )

            print(
                "summary:",
                topic.summary,
            )

            print(
                "keywords:",
                topic.keywords,
            )

            print(
                "entities:",
                topic.entities,
            )

            print(
                "confidence:",
                topic.confidence,
            )

            print()

    finally:
        connection.close()


if __name__ == "__main__":
    main()
