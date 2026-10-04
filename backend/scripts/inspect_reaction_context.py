from pathlib import Path

from app.pipeline.reaction_context import (
    build_reaction_context,
)
from app.repository.database import (
    connect_db,
)
from app.repository.reaction_match_repo import (
    list_reaction_matches_by_stream,
)


DB_PATH = Path(
    "aza_demo_v1.db"
)

STREAM_ID = (
    "c05f34e0-b116-5671-8013-5d63f144ca70"
)


def main() -> None:
    connection = connect_db(
        DB_PATH
    )

    try:
        matches = list_reaction_matches_by_stream(
            connection,
            stream_id=STREAM_ID,
        )

        print(
            "ReactionMatches:",
            len(matches),
        )

        if len(matches) < 2:
            raise RuntimeError(
                "not enough reaction matches"
            )

        # 就看我们之前讨论过的第 2 个 Match。
        match = matches[1]

        context = build_reaction_context(
            connection,
            reaction_match=match,
        )

        print()
        print("=" * 72)
        print(
            "ReactionMatch:",
            context.reaction_match_id,
        )
        print(
            "Highlight:",
            context.highlight_id,
        )
        print(
            "Part:",
            context.part_id,
        )

        print()
        print("[Transcript]")

        for item in context.transcripts:
            print(
                f"{item.start_ms:>8}"
                f" - "
                f"{item.end_ms:>8}"
                f" | "
                f"{item.text}"
            )

        print()
        print("[Danmaku]")

        print(
            "Raw danmaku:",
            context.raw_danmaku_count,
        )

        grouped_count = sum(
            group.count
            for group in context.reaction_groups
        )

        print(
            "Grouped danmaku:",
            grouped_count,
        )

        print(
            "Reaction groups:",
            len(context.reaction_groups),
        )

        print()

        for group in context.reaction_groups:
            print(
                f"x{group.count:<3} "
                f"{group.text}"
                f"  "
                f"[{group.first_timestamp_ms}"
                f" -> "
                f"{group.last_timestamp_ms}]"
            )

    finally:
        connection.close()


if __name__ == "__main__":
    main()