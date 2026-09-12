from collections import Counter

from app.domain.danmaku import Danmaku
from app.domain.signal_window import SignalWindow

    
BASE_STEP_MS = 10_000

WINDOW_SCALES_MS = (
    30_000,
    60_000,
    120_000,
)

# TODO 这里是否需要优化
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

def contains_any(
    text: str,
    markers: tuple[str, ...],
) -> bool:
    normalized = text.lower()

    return any(
        marker in normalized
        for marker in markers
    )

def is_laugh_reaction(
    text: str
) -> bool:
    return contains_any(
        text,
        LAUGH_MARKERS,
    )
    
def is_question_reaction(
    text: str,
) -> bool:
    return contains_any(
        text,
        QUESTION_MARKERS,
    )
    
def is_exclamation_reaction(
    text: str,
) -> bool:
    return contains_any(
        text,
        EXCLAMATION_MARKERS,
    )


def build_windows_for_part(
    stream_id: str,
    part_id: str,
    danmaku: list[Danmaku],
) -> list[SignalWindow]:
    
    """
    对一个 StreamPart 建立：

    30 秒
    60 秒
    120 秒

    三种尺度的滑动窗口。

    每 10 秒移动一次。
    """
    
    if not danmaku: return []
    
    max_timestamp = max(
        item.timestamp_ms for item in danmaku
    )
    
    windows: list[SignalWindow] = []
    
    for scale_ms in WINDOW_SCALES_MS:
        start_ms = 0
        
        while start_ms <= max_timestamp:
            end_ms = start_ms + scale_ms
            
            items = [
                item for item in danmaku
                if start_ms<=item.timestamp_ms<end_ms
            ]
            
            texts = [
                item.text for item in items if item.text
            ]
            
            text_counter = Counter(texts)
            
            danmaku_count = len(texts)
            
            unique_text_count = len(text_counter)
            
            if danmaku_count == 0:
                repetition_ratio = 0.0
                reaction_ratio = 0.0

                laugh_count = 0
                question_count = 0
                exclamation_count = 0
                
            else:
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
                    if is_laugh_reaction(text)
                )

                question_count = sum(
                    1
                    for text in texts
                    if is_question_reaction(text)
                )

                exclamation_count = sum(
                    1
                    for text in texts
                    if is_exclamation_reaction(text)
                )

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
                    scale_ms=scale_ms,
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
    当前值在这一组数据中处于什么位置。

    例如：

        0.98

    表示它高于大约 98% 的窗口。
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
    所有归一化都只和当前 Stream 自己比较。

    但不同 window scale 分开比较。

    30 秒窗口只和其他 30 秒窗口比；
    60 秒同理；
    120 秒同理。
    """
    
    for scale_ms in WINDOW_SCALES_MS:
        scale_windows = [
            window for window in windows
            if window.scale_ms == scale_ms
        ]
        
        if not scale_windows:
            continue

        density_values = [
            float(window.danmaku_count)
            for window in scale_windows
        ]

        repetition_values = [
            window.repetition_ratio
            for window in scale_windows
        ]

        reaction_values = [
            window.reaction_ratio
            for window in scale_windows
        ]
        
        for window in scale_windows:
            window.density_score = percentile_rank(
                float(window.danmaku_count),
                density_values,
            )

            window.repetition_score = percentile_rank(
                window.repetition_ratio,
                repetition_values,
            )

            window.reaction_score = percentile_rank(
                window.reaction_ratio,
                reaction_values,
            )

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
    stream_parts:

    [
        (
            part_id,
            [Danmaku, Danmaku, ...]
        ),
        ...
    ]

    先对每个 Part 建窗口，
    再把整场 Stream 放在一起归一化。
    """

    windows: list[SignalWindow] = []

    for part_id, danmaku in stream_parts:
        part_windows = build_windows_for_part(
            stream_id=stream_id,
            part_id=part_id,
            danmaku=danmaku,
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
    非正式的第一版 Peak Detector。

    同一 Part、同一尺度下：

        当前窗口 score
        同时高于左右相邻窗口

    就认为它是局部峰。

    当前只是用于观察数据，
    还不是最终 Event Detector。
    """

    peaks: list[SignalWindow] = []

    grouped: dict[
        tuple[str, int],
        list[SignalWindow],
    ] = {}

    for window in windows:
        key = (
            window.part_id,
            window.scale_ms,
        )

        grouped.setdefault(
            key,
            [],
        ).append(window)

    for group in grouped.values():
        group.sort(
            key=lambda item: item.start_ms
        )

        if len(group) < 3:
            continue

        for index in range(
            1,
            len(group) - 1,
        ):
            previous = group[index - 1]
            current = group[index]
            following = group[index + 1]

            if current.score < min_score:
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