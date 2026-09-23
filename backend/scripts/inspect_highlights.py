import argparse
import json
from collections import Counter
from pathlib import Path

from app.domain.danmaku import Danmaku
from app.domain.signal_window import SignalWindow
from app.event_pipeline.signals import (
    build_stream_signal_windows,
    find_local_peaks,
)
from app.repository.danmaku_repo import (
    list_danmaku_by_stream_part,
)
from app.repository.database import (
    connect_db,
)
from app.repository.stream_part_repo import (
    list_stream_parts,
)
from app.repository.stream_repo import (
    get_stream_by_id,
    list_streams,
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
        total_seconds
        % 3600
        // 60
    )

    seconds = (
        total_seconds % 60
    )

    if hours:
        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

    return (
        f"{minutes:02d}:"
        f"{seconds:02d}"
    )


def window_key(
    window: SignalWindow,
) -> tuple[str, int, int]:
    return (
        window.part_id,
        window.start_ms,
        window.end_ms,
    )


def overlaps(
    first: SignalWindow,
    second: SignalWindow,
) -> bool:
    if (
        first.part_id
        != second.part_id
    ):
        return False

    return not (
        first.end_ms
        <= second.start_ms
        or second.end_ms
        <= first.start_ms
    )


def choose_spaced(
    candidates: list[SignalWindow],
    *,
    limit: int,
    existing: list[SignalWindow] | None = None,
) -> list[SignalWindow]:
    """
    从候选里抽取互不重叠的窗口。

    因为当前窗口步长 10 秒、
    窗口长度 30 秒，
    如果不去重，很容易人工连续看三个
    几乎相同的窗口。
    """

    selected: list[
        SignalWindow
    ] = []

    blocked = list(
        existing or []
    )

    for candidate in candidates:
        if any(
            overlaps(
                candidate,
                other,
            )
            for other
            in (
                blocked
                + selected
            )
        ):
            continue

        selected.append(
            candidate
        )

        if (
            len(selected)
            >= limit
        ):
            break

    return selected


def evenly_sample(
    items: list[Danmaku],
    limit: int,
) -> list[Danmaku]:
    if (
        limit <= 0
        or not items
    ):
        return []

    if len(items) <= limit:
        return items

    if limit == 1:
        return [
            items[
                len(items) // 2
            ]
        ]

    return [
        items[
            round(
                index
                * (
                    len(items) - 1
                )
                / (
                    limit - 1
                )
            )
        ]
        for index
        in range(limit)
    ]


def get_window_danmaku(
    window: SignalWindow,
    danmaku_by_part: dict[
        str,
        list[Danmaku],
    ],
) -> list[Danmaku]:
    items = (
        danmaku_by_part.get(
            window.part_id,
            [],
        )
    )

    return [
        item
        for item in items
        if (
            window.start_ms
            <= item.timestamp_ms
            < window.end_ms
        )
    ]


def build_stream_windows(
    connection,
    stream_id: str,
) -> tuple[
    list[SignalWindow],
    dict[
        str,
        list[Danmaku],
    ],
]:
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

    danmaku_by_part: dict[
        str,
        list[Danmaku],
    ] = {}

    for part in parts:
        part_id = part[
            "part_id"
        ]

        danmaku = (
            list_danmaku_by_stream_part(
                connection=connection,
                stream_part_id=(
                    part["id"]
                ),
                stream_id=stream_id,
                part_id=part_id,
            )
        )

        stream_parts.append(
            (
                part_id,
                danmaku,
            )
        )

        danmaku_by_part[
            part_id
        ] = danmaku

    windows = (
        build_stream_signal_windows(
            stream_parts=stream_parts,
            stream_id=stream_id,
        )
    )

    return (
        windows,
        danmaku_by_part,
    )


def choose_samples(
    windows: list[SignalWindow],
    *,
    top_count: int,
    middle_count: int,
    low_count: int,
    min_highlight_score: float,
) -> dict[
    str,
    list[SignalWindow],
]:
    nonempty = [
        window
        for window in windows
        if (
            window.danmaku_count
            > 0
        )
    ]

    peaks = (
        find_local_peaks(
            windows,
            min_score=(
                min_highlight_score
            ),
        )
    )

    top = choose_spaced(
        peaks,
        limit=top_count,
    )

    middle_candidates = sorted(
        nonempty,
        key=lambda window: (
            abs(
                window.score
                - 0.5
            ),
            window.start_ms,
        ),
    )

    middle = choose_spaced(
        middle_candidates,
        limit=middle_count,
        existing=top,
    )

    low_candidates = sorted(
        nonempty,
        key=lambda window: (
            window.score,
            -window.danmaku_count,
        ),
    )

    low = choose_spaced(
        low_candidates,
        limit=low_count,
        existing=(
            top
            + middle
        ),
    )

    return {
        "TOP": top,
        "MIDDLE": middle,
        "LOW": low,
    }


def print_window(
    *,
    group: str,
    index: int,
    window: SignalWindow,
    danmaku: list[Danmaku],
    danmaku_lines: int,
) -> None:
    print()
    print(
        "-" * 72
    )

    print(
        f"[{group} #{index}] "
        f"{window.part_id} | "
        f"{format_time(window.start_ms)}"
        " - "
        f"{format_time(window.end_ms)}"
    )

    print(
        "score      = "
        f"{window.score:.3f}"
    )

    print(
        "density    = "
        f"{window.density_score:.3f}"
        " | repetition = "
        f"{window.repetition_score:.3f}"
        " | reaction = "
        f"{window.reaction_score:.3f}"
    )

    print(
        "danmaku    = "
        f"{window.danmaku_count}"
        " | unique = "
        f"{window.unique_text_count}"
    )

    print(
        "repeat ratio   = "
        f"{window.repetition_ratio:.3f}"
        " | reaction ratio = "
        f"{window.reaction_ratio:.3f}"
    )

    print(
        "laugh/question/exclamation = "
        f"{window.laugh_count}"
        "/"
        f"{window.question_count}"
        "/"
        f"{window.exclamation_count}"
    )

    counter = Counter(
        item.text.strip()
        for item in danmaku
        if item.text.strip()
    )

    print()
    print(
        "Top texts:"
    )

    for text, count in (
        counter.most_common(
            8
        )
    ):
        print(
            f"  {count:>3} × "
            f"{text}"
        )

    print()
    print(
        "Timeline sample:"
    )

    for item in evenly_sample(
        danmaku,
        danmaku_lines,
    ):
        print(
            "  "
            f"{format_time(item.timestamp_ms)} "
            f"{item.text}"
        )


def ask_label() -> str | None:
    """
    A = 明显强反应
    B = 有一定反应
    C = 普通 / 误报
    S = 跳过
    """

    while True:
        value = input(
            "\nLabel "
            "[A strong / B moderate / "
            "C ordinary / S skip]: "
        ).strip().upper()

        if value in {
            "A",
            "B",
            "C",
        }:
            return value

        if value in {
            "S",
            "",
        }:
            return None

        print(
            "请输入 A / B / C / S"
        )


def make_record(
    *,
    stream: dict,
    group: str,
    window: SignalWindow,
    danmaku: list[Danmaku],
    label: str | None,
) -> dict:
    counter = Counter(
        item.text.strip()
        for item in danmaku
        if item.text.strip()
    )

    return {
        "stream_id": (
            stream["id"]
        ),
        "stream_title": (
            stream["title"]
        ),
        "live_time": (
            stream["live_time"]
        ),
        "group": group,
        "part_id": (
            window.part_id
        ),
        "start_ms": (
            window.start_ms
        ),
        "end_ms": (
            window.end_ms
        ),
        "score": (
            window.score
        ),
        "density_score": (
            window.density_score
        ),
        "repetition_score": (
            window.repetition_score
        ),
        "reaction_score": (
            window.reaction_score
        ),
        "danmaku_count": (
            window.danmaku_count
        ),
        "repetition_ratio": (
            window.repetition_ratio
        ),
        "reaction_ratio": (
            window.reaction_ratio
        ),
        "laugh_count": (
            window.laugh_count
        ),
        "question_count": (
            window.question_count
        ),
        "exclamation_count": (
            window.exclamation_count
        ),
        "top_texts": [
            {
                "text": text,
                "count": count,
            }
            for text, count
            in counter.most_common(
                10
            )
        ],
        "label": label,
    }


def print_label_summary(
    records: list[dict],
) -> None:
    labeled = [
        item
        for item in records
        if item["label"]
        is not None
    ]

    if not labeled:
        return

    print()
    print(
        "=" * 72
    )

    print(
        "Manual Inspection Summary"
    )

    print(
        "=" * 72
    )

    for group in (
        "TOP",
        "MIDDLE",
        "LOW",
    ):
        group_items = [
            item
            for item in labeled
            if (
                item["group"]
                == group
            )
        ]

        if not group_items:
            continue

        counts = Counter(
            item["label"]
            for item in group_items
        )

        print(
            f"{group}: "
            f"A={counts['A']} "
            f"B={counts['B']} "
            f"C={counts['C']} "
            f"(n={len(group_items)})"
        )

        if group == "TOP":
            relevant = (
                counts["A"]
                + counts["B"]
            )

            print(
                "  Top A+B rate: "
                f"{relevant / len(group_items):.1%}"
            )

            print(
                "  Top A rate:   "
                f"{counts['A'] / len(group_items):.1%}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Manually inspect TOP / MIDDLE / LOW "
            "SignalWindows for Highlight detector "
            "acceptance."
        )
    )

    parser.add_argument(
        "--db",
        type=Path,
        required=True,
    )

    target_group = (
        parser
        .add_mutually_exclusive_group(
            required=True
        )
    )

    target_group.add_argument(
        "--vtuber-id",
    )

    target_group.add_argument(
        "--stream-id",
    )

    parser.add_argument(
        "--limit-streams",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--top",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--middle",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--low",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--min-highlight-score",
        type=float,
        default=0.85,
    )

    parser.add_argument(
        "--danmaku-lines",
        type=int,
        default=12,
    )

    parser.add_argument(
        "--label",
        action="store_true",
        help=(
            "交互式标注 A/B/C，"
            "并输出人工检查记录"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            ".local/eval/"
            "highlight_inspection.jsonl"
        ),
    )

    args = (
        parser.parse_args()
    )

    if (
        args.limit_streams
        < 1
    ):
        parser.error(
            "--limit-streams must be >= 1"
        )

    for name in (
        "top",
        "middle",
        "low",
    ):
        if (
            getattr(
                args,
                name,
            )
            < 0
        ):
            parser.error(
                f"--{name} must be >= 0"
            )

    if not (
        0.0
        <= args.min_highlight_score
        <= 1.0
    ):
        parser.error(
            "--min-highlight-score "
            "must be between 0 and 1"
        )

    db_path = (
        args.db
        .expanduser()
        .resolve()
    )

    connection = (
        connect_db(
            db_path
        )
    )

    records: list[
        dict
    ] = []

    try:
        if args.stream_id:
            stream = (
                get_stream_by_id(
                    connection,
                    args.stream_id,
                )
            )

            streams = (
                [stream]
                if stream
                else []
            )

        else:
            streams = (
                list_streams(
                    connection,
                    vtuber_id=(
                        args.vtuber_id
                    ),
                )[
                    : args.limit_streams
                ]
            )

        if not streams:
            raise RuntimeError(
                "No matching streams found"
            )

        for stream_index, stream in enumerate(
            streams,
            start=1,
        ):
            print()
            print(
                "=" * 72
            )

            print(
                f"[Stream "
                f"{stream_index}/"
                f"{len(streams)}]"
            )

            print(
                stream["title"]
            )

            print(
                "stream_id:",
                stream["id"],
            )

            (
                windows,
                danmaku_by_part,
            ) = build_stream_windows(
                connection,
                stream["id"],
            )

            samples = (
                choose_samples(
                    windows,
                    top_count=(
                        args.top
                    ),
                    middle_count=(
                        args.middle
                    ),
                    low_count=(
                        args.low
                    ),
                    min_highlight_score=(
                        args
                        .min_highlight_score
                    ),
                )
            )

            for group, group_windows in (
                samples.items()
            ):
                for index, window in enumerate(
                    group_windows,
                    start=1,
                ):
                    danmaku = (
                        get_window_danmaku(
                            window,
                            danmaku_by_part,
                        )
                    )

                    print_window(
                        group=group,
                        index=index,
                        window=window,
                        danmaku=danmaku,
                        danmaku_lines=(
                            args
                            .danmaku_lines
                        ),
                    )

                    label = (
                        ask_label()
                        if args.label
                        else None
                    )

                    records.append(
                        make_record(
                            stream=stream,
                            group=group,
                            window=window,
                            danmaku=danmaku,
                            label=label,
                        )
                    )

    finally:
        connection.close()

    if args.label:
        output = (
            args.output
            .expanduser()
        )

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output.write_text(
            "\n".join(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
                for record
                in records
            )
            + "\n",
            encoding="utf-8",
        )

        print_label_summary(
            records
        )

        print()
        print(
            "Saved:",
            output.resolve(),
        )


if __name__ == "__main__":
    main()