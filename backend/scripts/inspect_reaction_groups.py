from pathlib import Path

from app.pipeline.reaction_matcher import (
    _get_danmaku_for_highlight,
    _get_transcripts_for_highlight,
    _group_danmaku_reactions,
)
from app.repository.database import (
    connect_db,
)
from app.repository.highlight_repo import (
    list_highlights_by_stream,
)

DB_PATH = Path("aza_demo_v1.db")

STREAM_ID = "c05f34e0-b116-5671-8013-5d63f144ca70"


def main() -> None:
    connection = connect_db(DB_PATH)

    try:
        highlights = list_highlights_by_stream(
            connection,
            STREAM_ID,
        )

        print(
            "Highlights:",
            len(highlights),
        )

        # 先只看前三个，
        # 不要一次刷 48 个。
        for index, highlight in enumerate(
            highlights[:3],
            start=1,
        ):
            print()
            print("=" * 72)
            print(f"Highlight #{index}")
            print(
                "Part:",
                highlight.part_id,
            )
            print(
                "Window:",
                highlight.start_ms,
                "->",
                highlight.end_ms,
            )
            print(
                "Score:",
                highlight.score,
            )

            transcripts = _get_transcripts_for_highlight(
                connection,
                stream_id=STREAM_ID,
                part_id=highlight.part_id,
                highlight_start_ms=(highlight.start_ms),
                highlight_end_ms=(highlight.end_ms),
            )

            danmaku = _get_danmaku_for_highlight(
                connection,
                stream_id=STREAM_ID,
                part_id=highlight.part_id,
                highlight_start_ms=(highlight.start_ms),
                highlight_end_ms=(highlight.end_ms),
            )

            groups = _group_danmaku_reactions(danmaku)

            print()
            print("Transcript:")
            for item in transcripts:
                print(
                    f"  "
                    f"{item.start_ms:>8}"
                    f" - "
                    f"{item.end_ms:>8}"
                    f" | "
                    f"{item.text}"
                )

            print()
            print(
                "Raw danmaku:",
                len(danmaku),
            )
            print(
                "Reaction groups:",
                len(groups),
            )

            print()
            print("Top reaction groups:")

            for group in groups[:20]:
                print(
                    f"  x{group.count:<3} "
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
