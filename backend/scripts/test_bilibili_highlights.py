import argparse
from collections import Counter
from pathlib import Path

from app.domain.vtuber import Vtuber
from app.event_pipeline.highlights import (
    generate_highlights_for_stream,
)
from app.ingestion.bilibili_source import (
    BilibiliSource,
)
from app.ingestion.persist import (
    persist_archive_bundle,
)
from app.repository.database import (
    connect_db,
    init_db,
)


def format_time(
    timestamp_ms: int,
) -> str:
    total_seconds = (
        timestamp_ms // 1000
    )

    hours = (
        total_seconds // 3600
    )

    minutes = (
        total_seconds % 3600
        // 60
    )

    seconds = (
        total_seconds % 60
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{seconds:02d}"
    )


def get_top_texts(
    danmaku,
    *,
    part_id: str,
    start_ms: int,
    end_ms: int,
    top_n: int,
) -> list[
    tuple[str, int]
]:
    texts = [
        item.text.strip()
        for item in danmaku
        if (
            item.part_id
            == part_id
            and start_ms
            <= item.timestamp_ms
            < end_ms
            and item.text.strip()
        )
    ]

    counter = Counter(
        texts
    )

    return counter.most_common(
        top_n
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "bvid",
        help="Bilibili BV ID",
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=Path(
            "bilibili_highlight_test.db"
        ),
    )

    parser.add_argument(
        "--vtuber-id",
        default="aza",
    )

    parser.add_argument(
        "--vtuber-name",
        default="阿萨Aza",
    )

    parser.add_argument(
        "--auth-mode",
        choices=[
            "auto",
            "guest",
            "authenticated",
        ],
        default="authenticated",
    )

    parser.add_argument(
        "--min-score",
        type=float,
        default=0.85,
    )

    parser.add_argument(
        "--top",
        type=int,
        default=10,
    )

    parser.add_argument(
        "--top-texts",
        type=int,
        default=8,
    )

    args = parser.parse_args()

    vtuber = Vtuber(
        id=args.vtuber_id,
        display_name=(
            args.vtuber_name
        ),
    )

    print("=" * 70)
    print("Bilibili Highlight Smoke Test")
    print("=" * 70)

    print(
        "BVID:",
        args.bvid,
    )

    print(
        "VTuber:",
        vtuber.display_name,
    )

    print(
        "Auth mode:",
        args.auth_mode,
    )

    print()
    print(
        "正在抓取 Bilibili..."
    )

    source = BilibiliSource(
        bvid=args.bvid,
        vtuber=vtuber,
        auth_mode=args.auth_mode,
    )

    bundle = source.load()

    print()
    print("=" * 70)
    print("ArchiveBundle")
    print("=" * 70)

    print(
        "Title:",
        bundle.stream.title,
    )

    print(
        "Stream ID:",
        bundle.stream.id,
    )

    print(
        "Owner:",
        bundle.source_metadata.get(
            "owner"
        ),
    )

    print(
        "Authenticated:",
        bundle.source_metadata.get(
            "authenticated"
        ),
    )

    print(
        "Parts:",
        len(
            bundle.parts
        ),
    )

    print(
        "Danmaku:",
        len(
            bundle.danmaku
        ),
    )

    print()
    print(
        "各 Part 弹幕数量:"
    )

    for part in bundle.parts:
        count = sum(
            1
            for item
            in bundle.danmaku
            if (
                item.part_id
                == part.part_id
            )
        )

        print(
            f"  {part.part_id}: "
            f"{count}"
        )

    connection = connect_db(
        args.db
    )

    try:
        init_db(
            connection
        )

        print()
        print(
            "正在写入 SQLite..."
        )

        persist_archive_bundle(
            connection=connection,
            bundle=bundle,
        )

        print(
            "ArchiveBundle 写入完成。"
        )

        print()
        print(
            "正在生成 Highlights..."
        )

        highlights = (
            generate_highlights_for_stream(
                connection=connection,
                stream_id=(
                    bundle.stream.id
                ),
                min_score=(
                    args.min_score
                ),
            )
        )

        print()
        print("=" * 70)

        print(
            "Highlight 数量:",
            len(
                highlights
            ),
        )

        print("=" * 70)

        for (
            index,
            highlight,
        ) in enumerate(
            highlights[
                :args.top
            ],
            start=1,
        ):
            print()

            print(
                f"Highlight #{index}"
            )

            print(
                "  Part:",
                highlight.part_id,
            )

            print(
                "  Window:",
                format_time(
                    highlight.start_ms
                ),
                "-",
                format_time(
                    highlight.end_ms
                ),
            )

            print(
                "  Peak:",
                format_time(
                    highlight.peak_ms
                ),
            )

            print(
                "  Score:",
                f"{highlight.score:.3f}",
            )

            print(
                "  Density:",
                f"{highlight.density_score:.3f}",
                f"({highlight.danmaku_count})",
            )

            print(
                "  Repetition:",
                f"{highlight.repetition_score:.3f}",
                "ratio="
                f"{highlight.repetition_ratio:.3f}",
            )

            print(
                "  Reaction:",
                f"{highlight.reaction_score:.3f}",
                "ratio="
                f"{highlight.reaction_ratio:.3f}",
            )

            top_texts = (
                get_top_texts(
                    bundle.danmaku,
                    part_id=(
                        highlight.part_id
                    ),
                    start_ms=(
                        highlight.start_ms
                    ),
                    end_ms=(
                        highlight.end_ms
                    ),
                    top_n=(
                        args.top_texts
                    ),
                )
            )

            print(
                "  Top texts:"
            )

            for (
                text,
                count,
            ) in top_texts:
                print(
                    f"    {count:>4} × "
                    f"{text}"
                )

    finally:
        connection.close()

    print()
    print("=" * 70)
    print(
        "完成。DB:",
        args.db.resolve(),
    )
    print("=" * 70)


if __name__ == "__main__":
    main()