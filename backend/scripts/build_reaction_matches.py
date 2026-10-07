import argparse
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build ReactionMatches for "
            "a specified Stream."
        )
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

    connection = connect_db(
        args.db
    )

    try:
        matches = build_reaction_matches(
            connection,
            stream_id=args.stream_id,
        )

        print(
            "Built ReactionMatches:",
            len(matches),
        )

        persisted = list_reaction_matches_by_stream(
            connection,
            stream_id=args.stream_id,
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

            print(
                f"ReactionMatch #{index}"
            )

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
                len(
                    match.transcript_segment_ids
                ),
            )

            print(
                "  danmaku:",
                len(
                    match.danmaku_ids
                ),
            )

            print(
                "  matcher:",
                match.matcher_version,
            )

    finally:
        connection.close()


if __name__ == "__main__":
    main()