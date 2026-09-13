import re
from collections import Counter

from app.domain.danmaku import Danmaku
from app.domain.signal_window import SignalWindow


# 每隔 10 秒检查一次新的 30 秒窗口。
BASE_STEP_MS = 10_000

# V0 中 Atomic Event 固定为约 30 秒的高光片段。
EVENT_WINDOW_MS = 30_000


LAUGH_MARKERS = (
    "哈哈",
    "hhh",
    "www",
    "草",
    "笑死",
    "绷不住",
)

QUESTION_MARKERS = (
    "?",
    "？",
)

EXCLAMATION_MARKERS = (
    "!",
    "！",
)


# 纯问号弹幕：
#
# ?
# ???
# ？
# ？？？？？
#
# 都归一化成 <QUESTION>
QUESTION_PATTERN = re.compile(
    r"^[?？]+$"
)


# 蜜言应援弹幕：
#
# \蜜言/
# \蜜言/\蜜言/
# \蜜言/\蜜言/\蜜言/
#
# 都归一化成 <MIKOTO_CHANT>
MIKOTO_CHANT_PATTERN = re.compile(
    r"^(?:\\蜜言/)+$"
)


def contains_any(
    text: str,
    markers: tuple[str, ...],
) -> bool:
    """
    判断文本中是否包含 markers 中任意一个标记。
    """

    normalized = text.lower()

    return any(
        marker in normalized
        for marker in markers
    )


def is_laugh_reaction(
    text: str,
) -> bool:
    """
    判断是否属于笑声 / 搞笑反应。
    """

    return contains_any(
        text,
        LAUGH_MARKERS,
    )


def is_question_reaction(
    text: str,
) -> bool:
    """
    判断弹幕中是否包含问号反应。
    """

    return contains_any(
        text,
        QUESTION_MARKERS,
    )


def is_exclamation_reaction(
    text: str,
) -> bool:
    """
    判断弹幕中是否包含感叹号反应。
    """

    return contains_any(
        text,
        EXCLAMATION_MARKERS,
    )


def normalize_signal_text(
    text: str,
) -> str:
    """
    将形式不同、但对于 Signal Detection
    意义相同的弹幕归一化。

    注意：

    这里只用于统计，
    不会修改数据库中的原始弹幕。
    """

    text = text.strip()

    if QUESTION_PATTERN.fullmatch(text):
        return "<QUESTION>"

    if MIKOTO_CHANT_PATTERN.fullmatch(text):
        return "<MIKOTO_CHANT>"

    return text


def build_windows_for_part(
    stream_id: str,
    part_id: str,
    danmaku: list[Danmaku],
) -> list[SignalWindow]:
    """
    将一个 StreamPart 切成连续的 30 秒滑动窗口。

    窗口长度：

        30 秒

    移动步长：

        10 秒

    因此会产生：

        00:00 - 00:30
        00:10 - 00:40
        00:20 - 00:50
        00:30 - 01:00
        ...
    """

    if not danmaku:
        return []

    max_timestamp = max(
        item.timestamp_ms
        for item in danmaku
    )

    windows: list[SignalWindow] = []

    start_ms = 0

    while start_ms <= max_timestamp:
        end_ms = (
            start_ms
            + EVENT_WINDOW_MS
        )

        # 当前 30 秒窗口里的所有弹幕。
        items = [
            item
            for item in danmaku
            if (
                start_ms
                <= item.timestamp_ms
                < end_ms
            )
        ]

        # 原始干净弹幕文本。
        #
        # 后面 reaction 判断仍使用真实文本。
        texts = [
            item.text.strip()
            for item in items
            if item.text.strip()
        ]

        # Signal 专用文本。
        #
        # 例如：
        #
        # ?
        # ？？？
        #
        # 都会变成 <QUESTION>。
        signal_texts = [
            normalize_signal_text(
                text
            )
            for text in texts
        ]

        text_counter = Counter(
            signal_texts
        )

        danmaku_count = len(
            texts
        )

        unique_text_count = len(
            text_counter
        )

        if danmaku_count == 0:
            repetition_ratio = 0.0
            reaction_ratio = 0.0

            laugh_count = 0
            question_count = 0
            exclamation_count = 0

        else:
            # 重复次数。
            #
            # 如果：
            #
            # A A A B C
            #
            # 那么 A 多出来了 2 次，
            # repeated_count = 2。
            repeated_count = sum(
                count - 1
                for count in text_counter.values()
                if count > 1
            )

            repetition_ratio = (
                repeated_count
                / danmaku_count
            )

            laugh_count = sum(
                1
                for text in texts
                if is_laugh_reaction(
                    text
                )
            )

            question_count = sum(
                1
                for text in texts
                if is_question_reaction(
                    text
                )
            )

            exclamation_count = sum(
                1
                for text in texts
                if is_exclamation_reaction(
                    text
                )
            )

            # 当前允许一条弹幕同时属于多个 reaction 类别。
            #
            # 所以最终用 min(..., 1.0)
            # 避免比例超过 1。
            reaction_count = (
                laugh_count
                + question_count
                + exclamation_count
            )

            reaction_ratio = min(
                reaction_count
                / danmaku_count,
                1.0,
            )

        windows.append(
            SignalWindow(
                stream_id=stream_id,
                part_id=part_id,
                start_ms=start_ms,
                end_ms=end_ms,
                scale_ms=EVENT_WINDOW_MS,
                danmaku_count=danmaku_count,
                unique_text_count=unique_text_count,
                repetition_ratio=repetition_ratio,
                reaction_ratio=reaction_ratio,
                laugh_count=laugh_count,
                question_count=question_count,
                exclamation_count=exclamation_count,
            )
        )

        start_ms += BASE_STEP_MS

    return windows


def percentile_rank(
    value: float,
    values: list[float],
) -> float:
    """
    计算 value 在当前直播中的相对位置。

    例如：

        0.98

    大致表示：

        当前值高于本场直播约 98% 的窗口。
    """

    if not values:
        return 0.0

    less_or_equal = sum(
        1
        for item in values
        if item <= value
    )

    return (
        less_or_equal
        / len(values)
    )


def normalize_stream_windows(
    windows: list[SignalWindow],
) -> list[SignalWindow]:
    """
    将窗口统计相对于“当前这一场直播”
    进行归一化。

    V0 现在只有统一的 30 秒窗口，
    因此所有窗口可以直接彼此比较。
    """

    if not windows:
        return []

    density_values = [
        float(
            window.danmaku_count
        )
        for window in windows
    ]

    repetition_values = [
        window.repetition_ratio
        for window in windows
    ]

    reaction_values = [
        window.reaction_ratio
        for window in windows
    ]

    for window in windows:
        window.density_score = (
            percentile_rank(
                float(
                    window.danmaku_count
                ),
                density_values,
            )
        )

        window.repetition_score = (
            percentile_rank(
                window.repetition_ratio,
                repetition_values,
            )
        )

        window.reaction_score = (
            percentile_rank(
                window.reaction_ratio,
                reaction_values,
            )
        )

        # V0 临时权重。
        #
        # 现在主要用于真实数据实验，
        # 不是最终算法。
        window.score = (
            0.5
            * window.density_score
            + 0.25
            * window.repetition_score
            + 0.25
            * window.reaction_score
        )

    return windows


def build_stream_signal_windows(
    stream_parts: list[
        tuple[
            str,
            list[Danmaku],
        ]
    ],
    stream_id: str,
) -> list[SignalWindow]:
    """
    为一整场直播建立 30 秒 SignalWindow。

    每个 Part 独立切窗口，
    但最后整场直播统一做归一化。

    因此：

        density_score

    表示当前窗口相对于整场直播
    其他窗口的异常程度。
    """

    windows: list[SignalWindow] = []

    for part_id, danmaku in stream_parts:
        part_windows = (
            build_windows_for_part(
                stream_id=stream_id,
                part_id=part_id,
                danmaku=danmaku,
            )
        )

        windows.extend(
            part_windows
        )

    return normalize_stream_windows(
        windows
    )


def find_local_peaks(
    windows: list[SignalWindow],
    min_score: float = 0.85,
) -> list[SignalWindow]:
    """
    从 30 秒窗口序列中找局部高光候选。

    对同一个 Part：

        previous
        current
        following

    如果 current：

    1. score >= min_score
    2. score >= previous
    3. score >= following

    则认为当前 30 秒是一个
    Atomic Event Candidate。
    """

    peaks: list[SignalWindow] = []

    grouped: dict[
        str,
        list[SignalWindow],
    ] = {}

    # 不同 Part 的局部时间不能互相比较，
    # 所以按 part_id 分组。
    for window in windows:
        grouped.setdefault(
            window.part_id,
            [],
        ).append(window)

    for group in grouped.values():
        group.sort(
            key=lambda item: (
                item.start_ms
            )
        )

        if len(group) < 3:
            continue

        for index in range(
            1,
            len(group) - 1,
        ):
            previous = (
                group[index - 1]
            )

            current = (
                group[index]
            )

            following = (
                group[index + 1]
            )

            if (
                current.score
                < min_score
            ):
                continue

            if (
                current.score
                >= previous.score
                and current.score
                >= following.score
            ):
                peaks.append(
                    current
                )

    peaks.sort(
        key=lambda item: item.score,
        reverse=True,
    )

    return peaks


def find_peak_ms(
    peak_window: SignalWindow,
    danmaku: list[Danmaku],
) -> int:
    """
    在一个 30 秒高光窗口内部，
    再找最强的 10 秒。

    返回最强 10 秒的中心时间。

    注意：

    Atomic Event 本身仍然是 30 秒。

    peak_ms 只是告诉我们：

        这 30 秒中最核心的位置在哪。
    """

    if not danmaku:
        return (
            peak_window.start_ms
            + peak_window.end_ms
        ) // 2

    best_start_ms = (
        peak_window.start_ms
    )

    # 比较顺序：
    #
    # 1. 弹幕数量
    # 2. 强反应数量
    # 3. 复读数量
    best_key = (
        -1,
        -1,
        -1,
    )

    for start_ms in range(
        peak_window.start_ms,
        peak_window.end_ms,
        BASE_STEP_MS,
    ):
        end_ms = min(
            start_ms + BASE_STEP_MS,
            peak_window.end_ms,
        )

        items = [
            item
            for item in danmaku
            if (
                start_ms
                <= item.timestamp_ms
                < end_ms
            )
        ]

        danmaku_count = len(
            items
        )

        reaction_count = sum(
            1
            for item in items
            if (
                is_laugh_reaction(
                    item.text
                )
                or is_question_reaction(
                    item.text
                )
                or is_exclamation_reaction(
                    item.text
                )
            )
        )

        signal_texts = [
            normalize_signal_text(
                item.text
            )
            for item in items
            if item.text.strip()
        ]

        text_counter = Counter(
            signal_texts
        )

        repeated_count = sum(
            count - 1
            for count
            in text_counter.values()
            if count > 1
        )

        current_key = (
            danmaku_count,
            reaction_count,
            repeated_count,
        )

        if current_key > best_key:
            best_key = current_key
            best_start_ms = start_ms

    peak_ms = (
        best_start_ms
        + BASE_STEP_MS // 2
    )

    return min(
        peak_ms,
        peak_window.end_ms,
    )