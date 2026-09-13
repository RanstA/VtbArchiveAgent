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
    把毫秒时间戳转换成：

        HH:MM:SS

    例如：

        1_060_000 ms
        ->
        00:17:40
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
    找出某个 Peak Window 时间范围内
    出现次数最多的弹幕文本。

    当前直接按照原始干净文本统计，
    不进行 signal normalization。

    所以输出仍然可以看到：

        ？
        ？？
        ？？？

    这种真实弹幕形式。
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
        help="显示多少个 Peak",
    )

    parser.add_argument(
        "--top-texts",
        type=int,
        default=8,
        help="每个 Peak 显示多少条高频弹幕",
    )

    args = parser.parse_args()

    connection = connect_db(
        DB_PATH
    )

    try:
        # --------------------------------
        # 1. 根据标题搜索 Stream
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
        # 2. 读取所有 StreamPart
        # --------------------------------

        parts = list_stream_parts(
            connection=connection,
            stream_id=stream_id,
        )

        # 给 Event Detector 使用：
        #
        # [
        #     (
        #         part_id,
        #         [Danmaku, ...]
        #     )
        # ]
        stream_parts: list[
            tuple[
                str,
                list[Danmaku],
            ]
        ] = []

        # 保存：
        #
        # part_id
        # ->
        # 该 Part 的全部 Danmaku
        #
        # 后面找 peak_ms 和打印 Top Texts 都要用。
        danmaku_by_part_id: dict[
            str,
            list[Danmaku],
        ] = {}

        total_danmaku = 0

        for part in parts:
            part_id = part["part_id"]

            danmaku = list_danmaku_by_stream_part(
                connection=connection,
                stream_part_id=part["id"],
                stream_id=stream_id,
                part_id=part_id,
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
        # 3. 构造多尺度 Signal Windows
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
        # 4. 找 Local Peak Windows
        # --------------------------------

        peaks = find_local_peaks(
            windows=windows,
            min_score=0.85,
        )

        print(
            "Peak 数量:",
            len(peaks),
        )

        # --------------------------------
        # 5. 打印 Peak
        # --------------------------------

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
                "Window:",
                f"{format_time(peak.start_ms)}"
                " - "
                f"{format_time(peak.end_ms)}",
            )

            print(
                "Scale:",
                f"{peak.scale_ms // 1000}s",
            )

            # --------------------------------
            # 找这个 Peak Window 内部
            # 最强 10 秒对应的中心时间。
            # --------------------------------

            part_danmaku = (
                danmaku_by_part_id.get(
                    peak.part_id,
                    [],
                )
            )

            peak_ms = find_peak_ms(
                peak_window=peak,
                danmaku=part_danmaku,
            )

            print(
                "Peak time:",
                format_time(
                    peak_ms
                ),
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

            # --------------------------------
            # 打印这个 Peak Window 内
            # 最常见的真实弹幕文本。
            # --------------------------------

            top_texts = get_top_texts(
                danmaku=part_danmaku,
                start_ms=peak.start_ms,
                end_ms=peak.end_ms,
                top_n=args.top_texts,
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