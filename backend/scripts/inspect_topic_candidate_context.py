from pathlib import Path

from app.pipeline.topic_candidate import (
    build_topic_candidates,
)
from app.pipeline.topic_context import (
    build_topic_candidate_context,
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

CANDIDATE_INDEX = 11


def main() -> None:
    connection = connect_db(
        DB_PATH
    )

    try:
        candidates = build_topic_candidates(
            connection,
            stream_id=STREAM_ID,
        )

        if len(candidates) <= CANDIDATE_INDEX:
            raise RuntimeError(
                "candidate index out of range"
            )

        candidate = candidates[
            CANDIDATE_INDEX
        ]

        print("=" * 72)
        print(
            "Candidate:",
            CANDIDATE_INDEX + 1,
        )
        print(
            "Parts:",
            candidate.source_part_ids,
        )
        print(
            "ReactionMatches:",
            len(
                candidate.reaction_match_ids
            ),
        )
        print(
            "Range:",
            candidate.start_ms,
            "->",
            candidate.end_ms,
        )
        print("=" * 72)
        print()

        context_text = (
            build_topic_candidate_context(
                connection,
                candidate=candidate,
            )
        )

        print(context_text)

    finally:
        connection.close()


if __name__ == "__main__":
    main()