from app.config.settings import settings
from app.event_pipeline.events import (
    merge_highlights,
)
from app.repository.database import (
    connect_db,
)
from app.repository.highlight_repo import (
    list_highlights_by_stream,
)
from app.repository.stream_repo import (
    list_streams,
)


MERGE_GAPS_MS = [
    10_000,
    20_000,
    30_000,
]

PREVIEW_GAP_MS = 20_000


def main() -> None:
    connection = connect_db(
        settings.database_path
    )

    totals = {
        gap_ms: {
            "highlights": 0,
            "candidates": 0,
            "singletons": 0,
        }
        for gap_ms in MERGE_GAPS_MS
    }

    try:
        streams = list_streams(
            connection
        )

        for stream in reversed(streams):
            stream_id = stream["id"]

            highlights = (
                list_highlights_by_stream(
                    connection,
                    stream_id,
                )
            )

            if not highlights:
                continue

            print()
            print("=" * 80)
            print(
                f"Stream: {stream['title']}"
            )
            print(
                f"ID: {stream_id}"
            )
            print(
                f"Highlights: {len(highlights)}"
            )

            preview_candidates = []

            for gap_ms in MERGE_GAPS_MS:
                candidates = merge_highlights(
                    highlights,
                    merge_gap_ms=gap_ms,
                )

                totals[
                    gap_ms
                ]["highlights"] += len(
                    highlights
                )

                totals[
                    gap_ms
                ]["candidates"] += len(
                    candidates
                )

                totals[
                    gap_ms
                ]["singletons"] += sum(
                    1
                    for candidate
                    in candidates
                    if len(
                        candidate.source_highlight_ids
                    ) == 1
                )

                print(
                    f"  gap={gap_ms // 1000:>2}s "
                    f"→ EventCandidates: "
                    f"{len(candidates)}"
                )

                if (
                    gap_ms
                    == PREVIEW_GAP_MS
                ):
                    preview_candidates = (
                        candidates
                    )

            print(
                f"Preview "
                f"(gap={PREVIEW_GAP_MS // 1000}s):"
            )

            for index, candidate in enumerate(
                preview_candidates[:5],
                start=1,
            ):
                duration_seconds = (
                    candidate.end_ms
                    - candidate.start_ms
                ) / 1000

                print(
                    f"  [{index}] "
                    f"part={candidate.part_id} | "
                    f"{candidate.start_ms} "
                    f"→ {candidate.end_ms} "
                    f"({duration_seconds:.1f}s) | "
                    f"highlights="
                    f"{len(candidate.source_highlight_ids)}"
                )

        print()
        print("=" * 80)
        print("MERGE GAP SWEEP")

        for gap_ms in MERGE_GAPS_MS:
            stats = totals[
                gap_ms
            ]

            highlight_count = (
                stats["highlights"]
            )

            candidate_count = (
                stats["candidates"]
            )

            singleton_count = (
                stats["singletons"]
            )

            candidate_ratio = (
                candidate_count
                / highlight_count
                if highlight_count
                else 0.0
            )

            singleton_ratio = (
                singleton_count
                / candidate_count
                if candidate_count
                else 0.0
            )

            print(
                f"gap={gap_ms // 1000:>2}s | "
                f"highlights={highlight_count:>3} | "
                f"candidates={candidate_count:>3} | "
                f"candidate/highlight="
                f"{candidate_ratio:.3f} | "
                f"singletons="
                f"{singleton_ratio:.3f}"
            )

    finally:
        connection.close()


if __name__ == "__main__":
    main()