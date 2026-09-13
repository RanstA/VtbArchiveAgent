import argparse
from collections import Counter
from pathlib import Path

from app.domain.danmaku import Danmaku
from app.event_pipeline.signals import (
    build_stream_signal_windows,
    find_local_peaks,
    find_peak_ms,
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
    """
    毫秒转 HH:MM:SS。
    """

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


def get_top_texts(
    danmaku: list[Danmaku],
    start_ms: int,
    end_ms: int,
    top_n: int = 8,
) -> list[tuple[str, int]]:
    """
    获取某个 30 秒候选片段中
    最常出现的真实弹幕文本。

    这里故意不用 Signal Normalization，
    因为我们希望人工检查时看到真实弹幕。
    """

    texts = [
        item.text.strip()
        for item in danmaku
        if (
            start_ms
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
        help="显示多少个高光候选",
    )

    parser.add_argument(
        "--top-texts",
        type=int,
        default=8,
        help="每个候选显示多少条高频弹幕",
    )

    args = parser.parse_args()

    connection = connect_db(
        DB_PATH
    )

    try:
        # --------------------------------
        # 1. 搜索直播
        # --------------------------------

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

        # --------------------------------
        # 2. 读取所有 Part + Danmaku
        # --------------------------------

        parts = list_stream_parts(
            connection=connection,
            stream_id=stream_id,
        )

        stream_parts: list[
            tuple[
                str,
                list[Danmaku],
            ]
        ] = []

        danmaku_by_part_id: dict[
            str,
            list[Danmaku],
        ] = {}

        total_danmaku = 0

        for part in parts:
            part_id = part["part_id"]

            danmaku = (
                list_danmaku_by_stream_part(
                    connection=connection,
                    stream_part_id=part["id"],
                    stream_id=stream_id,
                    part_id=part_id,
                )
            )

            total_danmaku += len(
                danmaku
            )

            stream_parts.append(
                (
                    part_id,
                    danmaku,
                )
            )

            danmaku_by_part_id[
                part_id
            ] = danmaku

            print(
                f"Part {part_id} | "
                f"danmaku={len(danmaku)}"
            )

        print()

        print(
            "总弹幕:",
            total_danmaku,
        )

        # --------------------------------
        # 3. 生成固定 30 秒 SignalWindow
        # --------------------------------

        windows = (
            build_stream_signal_windows(
                stream_parts=stream_parts,
                stream_id=stream_id,
            )
        )

        print(
            "30s Signal Window 数量:",
            len(windows),
        )

        # --------------------------------
        # 4. 找局部峰
        #
        # 一个 Local Peak
        # 就暂时视为一个
        # Highlight Candidate。
        # --------------------------------

        events = find_local_peaks(
            windows=windows,
            min_score=0.85,
        )

        print(
            "Highlight Candidate 数量:",
            len(events),
        )

        # --------------------------------
        # 5. 输出结果
        # --------------------------------

        print()
        print("=" * 70)

        print(
            f"Top {args.top} "
            "Highlight Candidates"
        )

        print("=" * 70)

        for index, event in enumerate(
            events[: args.top],
            start=1,
        ):
            part_danmaku = (
                danmaku_by_part_id.get(
                    event.part_id,
                    [],
                )
            )

            peak_ms = find_peak_ms(
                peak_window=event,
                danmaku=part_danmaku,
            )

            top_texts = get_top_texts(
                danmaku=part_danmaku,
                start_ms=event.start_ms,
                end_ms=event.end_ms,
                top_n=args.top_texts,
            )

            print()

            print(
                f"Highlight #{index}"
            )

            print(
                "Part:",
                event.part_id,
            )

            print(
                "Window:",
                f"{format_time(event.start_ms)}"
                " - "
                f"{format_time(event.end_ms)}",
            )

            print(
                "Peak time:",
                format_time(
                    peak_ms
                ),
            )

            print(
                "score:",
                f"{event.score:.3f}",
            )

            print(
                "density:",
                f"{event.density_score:.3f}",
                f"(count={event.danmaku_count})",
            )

            print(
                "repetition:",
                f"{event.repetition_score:.3f}",
                f"(ratio={event.repetition_ratio:.3f})",
            )

            print(
                "reaction:",
                f"{event.reaction_score:.3f}",
                f"(ratio={event.reaction_ratio:.3f})",
            )

            print(
                "reaction detail:",
                f"laugh={event.laugh_count}, "
                f"question={event.question_count}, "
                f"exclamation={event.exclamation_count}",
            )

            print(
                "Top texts:"
            )

            if not top_texts:
                print(
                    "  (无弹幕)"
                )

            else:
                for text, count in top_texts:
                    print(
                        f"  {count:>4} × {text}"
                    )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
