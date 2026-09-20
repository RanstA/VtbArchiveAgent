import argparse
import sqlite3
from pathlib import Path

from app.domain.highlight import Highlight
from app.event_pipeline.highlights import (
    DEFAULT_MIN_SCORE,
    generate_highlights_for_stream,
)
from app.repository.database import (
    connect_db,
    init_db,
)
from app.repository.stream_part_repo import (
    list_stream_parts,
)
from app.repository.stream_repo import (
    list_streams,
)


def format_time(
    timestamp_ms: int,
) -> str:
    total_seconds = (
        timestamp_ms
        // 1000
    )

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

    if hours > 0:
        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

    return (
        f"{minutes:02d}:"
        f"{seconds:02d}"
    )


def select_streams(
    connection: sqlite3.Connection,
    *,
    stream_id: str | None = None,
    vtuber_id: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """
    根据 CLI 参数选择待检测 Stream。

    两种模式二选一：

        --stream-id
        --vtuber-id
    """

    if (
        stream_id is None
        and vtuber_id is None
    ):
        raise ValueError(
            "stream_id or vtuber_id "
            "must be provided"
        )

    if (
        stream_id is not None
        and vtuber_id is not None
    ):
        raise ValueError(
            "stream_id and vtuber_id "
            "cannot be used together"
        )

    if stream_id is not None:
        stream_id = (
            stream_id.strip()
        )

        if not stream_id:
            raise ValueError(
                "stream_id cannot be empty"
            )

        rows = list_streams(
            connection=connection,
        )

        selected = [
            row
            for row in rows
            if (
                row["id"]
                == stream_id
            )
        ]

    else:
        assert vtuber_id is not None

        vtuber_id = (
            vtuber_id.strip()
        )

        if not vtuber_id:
            raise ValueError(
                "vtuber_id cannot be empty"
            )

        selected = list_streams(
            connection=connection,
            vtuber_id=vtuber_id,
        )

    if limit is not None:
        if limit < 1:
            raise ValueError(
                "limit must be >= 1"
            )

        selected = selected[
            :limit
        ]

    return selected


def generate_for_stream(
    connection: sqlite3.Connection,
    stream: dict,
    *,
    min_score: float,
) -> tuple[
    dict,
    list[Highlight],
]:
    """
    对单场 Stream 执行 Highlight Detection。

    单场失败不会影响后续批处理。
    """

    result = {
        "stream_id": stream["id"],
        "vtuber_id": (
            stream["vtuber_id"]
        ),
        "title": stream["title"],
        "has_danmaku": (
            stream["has_danmaku"]
        ),
        "parts": 0,
        "highlights": 0,
        "top_score": None,
        "status": None,
        "error": None,
    }

    try:
        parts = list_stream_parts(
            connection=connection,
            stream_id=stream["id"],
        )

        highlights = (
            generate_highlights_for_stream(
                connection=connection,
                stream_id=stream["id"],
                min_score=min_score,
            )
        )

        result["parts"] = len(
            parts
        )

        result["highlights"] = len(
            highlights
        )

        if highlights:
            result["top_score"] = max(
                item.score
                for item in highlights
            )

        result["status"] = "ok"

        return (
            result,
            highlights,
        )

    except Exception as exc:
        if connection.in_transaction:
            connection.rollback()

        result["status"] = "failed"
        result["error"] = str(
            exc
        )

        return (
            result,
            [],
        )


def print_highlight(
    index: int,
    highlight: Highlight,
) -> None:
    print(
        f"    #{index} "
        f"{highlight.part_id} | "
        f"{format_time(highlight.start_ms)}"
        " - "
        f"{format_time(highlight.end_ms)}"
        " | peak="
        f"{format_time(highlight.peak_ms)}"
        " | score="
        f"{highlight.score:.3f}"
    )

    print(
        "       "
        f"density="
        f"{highlight.density_score:.3f} "
        f"repetition="
        f"{highlight.repetition_score:.3f} "
        f"reaction="
        f"{highlight.reaction_score:.3f}"
    )

    print(
        "       "
        f"danmaku="
        f"{highlight.danmaku_count} "
        f"repeat_ratio="
        f"{highlight.repetition_ratio:.3f} "
        f"reaction_ratio="
        f"{highlight.reaction_ratio:.3f}"
    )


def print_summary(
    results: list[dict],
) -> None:
    succeeded = [
        item
        for item in results
        if item["status"] == "ok"
    ]

    failed = [
        item
        for item in results
        if item["status"] == "failed"
    ]

    print()
    print("=" * 70)
    print("Highlight Detection 完成")
    print("=" * 70)

    print(
        "处理 Stream:",
        len(results),
    )

    print(
        "成功:",
        len(succeeded),
    )

    print(
        "失败:",
        len(failed),
    )

    print(
        "Highlight 总数:",
        sum(
            item["highlights"]
            for item in succeeded
        ),
    )

    if failed:
        print()
        print(
            "=== 失败项 ==="
        )

        for item in failed:
            print(
                item["title"]
            )

            print(
                "  ",
                item["error"],
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Highlights from "
            "persisted Danmaku."
        )
    )

    parser.add_argument(
        "--db",
        type=Path,
        required=True,
        help=(
            "已完成 Archive 导入的 "
            "SQLite 数据库"
        ),
    )

    target_group = (
        parser.add_mutually_exclusive_group(
            required=True
        )
    )

    target_group.add_argument(
        "--stream-id",
        help=(
            "只检测指定 Stream"
        ),
    )

    target_group.add_argument(
        "--vtuber-id",
        help=(
            "检测指定 VTuber "
            "的所有 Stream"
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "只检测前 N 场，"
            "建议真实数据第一次先用 5"
        ),
    )

    parser.add_argument(
        "--min-score",
        type=float,
        default=(
            DEFAULT_MIN_SCORE
        ),
        help=(
            "Highlight 最低分数，"
            "默认 0.85"
        ),
    )

    parser.add_argument(
        "--show-top",
        type=int,
        default=3,
        help=(
            "每场打印分数最高的 "
            "N 个 Highlight"
        ),
    )

    args = parser.parse_args()

    if (
        not 0.0
        <= args.min_score
        <= 1.0
    ):
        parser.error(
            "--min-score must be "
            "between 0.0 and 1.0"
        )

    if (
        args.limit is not None
        and args.limit < 1
    ):
        parser.error(
            "--limit must be >= 1"
        )

    if args.show_top < 0:
        parser.error(
            "--show-top must be >= 0"
        )

    db_path = (
        args.db
        .expanduser()
        .resolve()
    )

    if not db_path.exists():
        raise FileNotFoundError(
            "Database does not exist: "
            f"{db_path}"
        )

    if not db_path.is_file():
        raise FileNotFoundError(
            "Database path is not a file: "
            f"{db_path}"
        )

    connection = connect_db(
        db_path
    )

    try:
        init_db(
            connection
        )

        streams = select_streams(
            connection=connection,
            stream_id=args.stream_id,
            vtuber_id=args.vtuber_id,
            limit=args.limit,
        )

        if not streams:
            raise RuntimeError(
                "No matching streams found."
            )

        print()
        print(
            "Database:",
            db_path,
        )

        print(
            "min_score:",
            args.min_score,
        )

        print(
            "待检测 Stream:",
            len(streams),
        )

        results: list[
            dict
        ] = []

        total = len(
            streams
        )

        for index, stream in enumerate(
            streams,
            start=1,
        ):
            print()

            print(
                f"[{index}/{total}] "
                f"{stream['title']}"
            )

            print(
                "  stream_id:",
                stream["id"],
            )

            print(
                "  has_danmaku:",
                stream[
                    "has_danmaku"
                ],
            )

            (
                result,
                highlights,
            ) = generate_for_stream(
                connection=connection,
                stream=stream,
                min_score=(
                    args.min_score
                ),
            )

            results.append(
                result
            )

            if (
                result["status"]
                == "failed"
            ):
                print(
                    "  FAILED |",
                    result["error"],
                )

                continue

            top_score = (
                "-"
                if (
                    result[
                        "top_score"
                    ]
                    is None
                )
                else (
                    f"{result['top_score']:.3f}"
                )
            )

            print(
                "  ok | "
                f"parts="
                f"{result['parts']} | "
                f"highlights="
                f"{result['highlights']} | "
                f"top_score="
                f"{top_score}"
            )

            if (
                args.show_top > 0
                and highlights
            ):
                print(
                    "  Top Highlights:"
                )

                for (
                    highlight_index,
                    highlight,
                ) in enumerate(
                    highlights[
                        :args.show_top
                    ],
                    start=1,
                ):
                    print_highlight(
                        highlight_index,
                        highlight,
                    )

        print_summary(
            results
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()