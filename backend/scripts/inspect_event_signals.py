import argparse
from pathlib import Path

from app.event_pipeline.signals import (
    build_stream_signal_windows,
    find_local_peaks,
)
from app.repository.database import connect_db
from app.repository.danmaku_repo import (
    list_danmaku_by_stream_part,
)
from app.repository.stream_part_repo import (
    list_stream_parts,
)
from app.repository.stream_repo import list_streams


DB_PATH = Path(
    "vtuber_archive.db"
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

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{seconds:02d}"
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--query",
        required=True,
        help="直播标题关键词",
    )

    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="显示多少个峰",
    )

    args = parser.parse_args()

    connection = connect_db(
        DB_PATH
    )

    try:
        streams = list_streams(
            connection=connection,
            query=args.query,
        )

        if len(streams) == 0:
            print(
                "没有找到匹配的 Stream"
            )

            return

        if len(streams) > 1:
            print(
                "找到多个 Stream，"
                "请使用更精确的关键词："
            )

            print()

            for stream in streams[:20]:
                print(
                    stream["title"]
                )

            return

        stream = streams[0]

        stream_id = stream["id"]

        print()
        print("=" * 70)

        print(
            stream["title"]
        )

        print(
            "Stream ID:",
            stream_id,
        )

        print("=" * 70)

        parts = list_stream_parts(
            connection=connection,
            stream_id=stream_id,
        )

        stream_parts = []

        total_danmaku = 0

        for part in parts:
            danmaku = list_danmaku_by_stream_part(
                connection=connection,
                stream_part_id=part["id"],
                stream_id=stream_id,
                part_id=part["part_id"],
            )

            total_danmaku += len(
                danmaku
            )

            stream_parts.append(
                (
                    part["part_id"],
                    danmaku,
                )
            )

            print(
                f"Part {part['part_id']} | "
                f"danmaku={len(danmaku)}"
            )

        print()
        print(
            "总弹幕:",
            total_danmaku,
        )

        # --------------------------------
        # 构造 Signal Windows
        # --------------------------------

        windows = build_stream_signal_windows(
            stream_parts=stream_parts,
            stream_id=stream_id,
        )

        print(
            "Signal Window 数量:",
            len(windows),
        )

        # --------------------------------
        # 找局部 Peak
        # --------------------------------

        peaks = find_local_peaks(
            windows=windows,
            min_score=0.85,
        )

        print(
            "Peak 数量:",
            len(peaks),
        )

        print()
        print("=" * 70)
        print(
            f"Top {args.top} Peaks"
        )
        print("=" * 70)

        for index, peak in enumerate(
            peaks[: args.top],
            start=1,
        ):
            print()

            print(
                f"#{index}"
            )

            print(
                "Part:",
                peak.part_id,
            )

            print(
                "时间:",
                f"{format_time(peak.start_ms)}"
                " - "
                f"{format_time(peak.end_ms)}",
            )

            print(
                "窗口:",
                f"{peak.scale_ms // 1000}s",
            )

            print(
                "score:",
                f"{peak.score:.3f}",
            )

            print(
                "density:",
                f"{peak.density_score:.3f}",
                f"(count={peak.danmaku_count})",
            )

            print(
                "repetition:",
                f"{peak.repetition_score:.3f}",
                f"(ratio={peak.repetition_ratio:.3f})",
            )

            print(
                "reaction:",
                f"{peak.reaction_score:.3f}",
                f"(ratio={peak.reaction_ratio:.3f})",
            )

            print(
                "reaction detail:",
                f"laugh={peak.laugh_count}, "
                f"question={peak.question_count}, "
                f"exclamation={peak.exclamation_count}",
            )

    finally:
        connection.close()


if __name__ == "__main__":
    main()