from pathlib import Path

from app.pipeline.topic_candidate import (
    build_topic_candidates,
)
from app.repository.database import (
    connect_db,
)


DB_PATH = Path(
    "aza_demo_v1.db"
)

STREAM_ID = (
    "c05f34e0-b116-5671-8013-5d63f144ca70"
)


def format_time(ms: int) -> str:
    total_seconds = ms // 1000

    hours = (
        total_seconds
        // 3600
    )

    minutes = (
        total_seconds
        % 3600
        // 60
    )

    seconds = (
        total_seconds
        % 60
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{seconds:02d}"
    )


def main() -> None:
    connection = connect_db(
        DB_PATH
    )

    try:
        candidates = (
            build_topic_candidates(
                connection,
                stream_id=STREAM_ID,
            )
        )

        print(
            "TopicCandidates:",
            len(candidates),
        )

        print()

        total_matches = 0

        for index, candidate in enumerate(
            candidates,
            start=1,
        ):
            match_count = len(
                candidate.reaction_match_ids
            )

            total_matches += (
                match_count
            )

            duration_ms = (
                candidate.end_ms
                - candidate.start_ms
            )

            print(
                f"Candidate #{index:02d}"
            )

            print(
                "  parts:",
                candidate.source_part_ids,
            )

            print(
                "  matches:",
                match_count,
            )

            print(
                "  range:",
                format_time(
                    candidate.start_ms
                ),
                "->",
                format_time(
                    candidate.end_ms
                ),
            )

            print(
                "  duration:",
                f"{duration_ms / 1000:.1f}s",
            )

            print()

        print(
            "Total ReactionMatches:",
            total_matches,
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()