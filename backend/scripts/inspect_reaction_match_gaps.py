from pathlib import Path

from app.repository.database import (
    connect_db,
)
from app.repository.highlight_repo import (
    get_highlight_by_id,
)
from app.repository.reaction_match_repo import (
    list_reaction_matches_by_stream,
)
from app.repository.stream_part_repo import (
    list_stream_parts,
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
        matches = (
            list_reaction_matches_by_stream(
                connection,
                stream_id=STREAM_ID,
            )
        )

        parts = list_stream_parts(
            connection,
            STREAM_ID,
        )

        part_offsets = {
            part["part_id"]: (
                part["start_offset_ms"]
            )
            for part in parts
        }

        windows = []

        for match in matches:
            highlight = (
                get_highlight_by_id(
                    connection,
                    match.highlight_id,
                )
            )

            if highlight is None:
                raise RuntimeError(
                    "missing highlight: "
                    f"{match.highlight_id}"
                )

            offset_ms = (
                part_offsets[
                    match.part_id
                ]
            )

            windows.append(
                (
                    match,
                    offset_ms
                    + highlight.start_ms,
                    offset_ms
                    + highlight.end_ms,
                )
            )

        print(
            "ReactionMatches:",
            len(windows),
        )

        print()

        for index in range(
            1,
            len(windows),
        ):
            previous = windows[
                index - 1
            ]
            current = windows[index]

            previous_match = previous[0]
            current_match = current[0]

            previous_end_ms = (
                previous[2]
            )

            current_start_ms = (
                current[1]
            )

            gap_ms = (
                current_start_ms
                - previous_end_ms
            )

            print(
                f"#{index:02d}"
                f" {previous_match.part_id}"
                f" -> "
                f"{current_match.part_id}"
                f" | gap="
                f"{gap_ms / 1000:>7.1f}s"
            )

    finally:
        connection.close()


if __name__ == "__main__":
    main()