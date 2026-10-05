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
from app.repository.database import (
    connect_db,
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
