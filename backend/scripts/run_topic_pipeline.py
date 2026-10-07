import argparse
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
from app.pipeline.topic_pipeline import (
    build_topic_segments_for_stream,
)
from app.repository.database import (
    connect_db,
    init_db,
)
from app.repository.reaction_match_repo import (
    list_reaction_matches_by_stream,
)
from app.repository.topic_segment_repo import (
    list_topic_segments_by_stream,
    replace_topic_segments_for_stream,
)


def format_ms(
    value: int,
) -> str:
    total_seconds = value // 1000

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    return f"{hours:02d}:" f"{minutes:02d}:" f"{seconds:02d}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=("Run Topic Pipeline for " "a specified Stream.")
    )

    parser.add_argument(
        "--db",
        type=Path,
        required=True,
        help="SQLite database path",
    )

    parser.add_argument(
        "--stream-id",
        required=True,
        help="Target Stream ID",
    )

    args = parser.parse_args()

    if not settings.event_scout_api_base_url:
        raise RuntimeError("EVENT_SCOUT_API_BASE_URL " "is not configured")

    if not settings.event_scout_model:
        raise RuntimeError("EVENT_SCOUT_MODEL " "is not configured")

    model = OpenAICompatibleChatClient(
        base_url=(settings.event_scout_api_base_url),
        api_key=(settings.event_scout_api_key),
        model=(settings.event_scout_model),
        timeout_seconds=(settings.event_scout_timeout_seconds),
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

    connection = connect_db(args.db)

    try:
        init_db(connection)

        reaction_matches = list_reaction_matches_by_stream(
            connection,
            stream_id=args.stream_id,
        )

        candidates = build_topic_candidates(
            connection,
            stream_id=args.stream_id,
        )

        print(
            "ReactionMatches:",
            len(reaction_matches),
        )

        print(
            "TopicCandidates:",
            len(candidates),
        )

        print()
        print("Running Topic Pipeline...")
        print()

        segments = build_topic_segments_for_stream(
            connection,
            stream_id=args.stream_id,
            analyzer=analyzer,
        )

        print(
            "Built TopicSegments:",
            len(segments),
        )

        print()
        print("Persisting...")

        replace_topic_segments_for_stream(
            connection,
            stream_id=args.stream_id,
            topic_segments=segments,
        )

        persisted = list_topic_segments_by_stream(
            connection,
            stream_id=args.stream_id,
        )

        assert len(persisted) == len(segments)

        print(
            "Persisted TopicSegments:",
            len(persisted),
        )

        print()
        print("=== FULL TIMELINE ===")
        print()

        for index, segment in enumerate(
            persisted,
            start=1,
        ):
            start = format_ms(segment.start_ms)

            end = format_ms(segment.end_ms)

            print(f"{index:02d}. " f"{start} - {end} | " f"{segment.title}")

            print(
                "    "
                f"salience="
                f"{segment.salience_score:.3f} "
                f"confidence="
                f"{segment.confidence:.2f}"
            )

            print(
                "    "
                f"RM="
                f"{len(segment.reaction_match_ids)} "
                f"transcripts="
                f"{len(segment.transcript_segment_ids)}"
            )

            print()

        print("=== PIPELINE COMPLETE ===")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
