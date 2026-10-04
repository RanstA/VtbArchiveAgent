from pathlib import Path

from app.pipeline.reaction_matcher import (
    build_reaction_matches,
)
from app.repository.database import (
    connect_db,
)
from app.repository.reaction_match_repo import (
    list_reaction_matches_by_stream,
)

DB_PATH = Path("aza_demo_v1.db")

STREAM_ID = "c05f34e0-b116-5671-8013-5d63f144ca70"


def main() -> None:
    connection = connect_db(DB_PATH)

    try:
        matches = build_reaction_matches(
            connection,
            stream_id=STREAM_ID,
        )

        print(
            "Built ReactionMatches:",
            len(matches),
        )

        persisted = list_reaction_matches_by_stream(
            connection,
            stream_id=STREAM_ID,
        )

        print(
            "Persisted ReactionMatches:",
            len(persisted),
        )

        print()
        print("First 5 matches:")

        for index, match in enumerate(
            persisted[:5],
            start=1,
        ):
            print()
            print(f"ReactionMatch #{index}")
            print(
                "  id:",
                match.id,
            )
            print(
                "  part:",
                match.part_id,
            )
            print(
                "  highlight:",
                match.highlight_id,
            )
            print(
                "  transcripts:",
                len(match.transcript_segment_ids),
            )
            print(
                "  danmaku:",
                len(match.danmaku_ids),
            )
            print(
                "  matcher:",
                match.matcher_version,
            )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
