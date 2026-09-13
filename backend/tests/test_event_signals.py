from app.domain.danmaku import Danmaku
from app.domain.signal_window import SignalWindow
from app.event_pipeline.signals import (
    build_stream_signal_windows,
    build_windows_for_part,
    find_local_peaks,
    find_peak_ms,
    normalize_signal_text,
    percentile_rank,
)


def make_window(
    score: float,
    start_ms: int = 0,
    stream_id: str = "stream-1",
    part_id: str = "part-1",
) -> SignalWindow:
    return SignalWindow(
        stream_id=stream_id,
        part_id=part_id,
        start_ms=start_ms,
        end_ms=start_ms + 30_000,
        scale_ms=30_000,
        danmaku_count=0,
        unique_text_count=0,
        repetition_ratio=0.0,
        reaction_ratio=0.0,
        laugh_count=0,
        question_count=0,
        exclamation_count=0,
        score=score,
    )


def make_danmaku(
    timestamp_ms: int,
    text: str = "普通弹幕",
    raw_text: str | None = None,
    stream_id: str = "stream-1",
    part_id: str = "part-1",
) -> Danmaku:
    return Danmaku(
        stream_id=stream_id,
        part_id=part_id,
        timestamp_ms=timestamp_ms,
        raw_text=raw_text if raw_text is not None else text,
        text=text,
    )


def test_percentile_rank_all_zero_values_are_zero() -> None:
    values = [0.0, 0.0, 0.0]

    assert [
        percentile_rank(value, values)
        for value in values
    ] == [0.0, 0.0, 0.0]


def test_percentile_rank_tied_low_values_do_not_score_high() -> None:
    values = [0.0, 0.0, 1.0, 2.0]

    assert percentile_rank(0.0, values) == 0.0
    assert percentile_rank(1.0, values) == 2 / 3
    assert percentile_rank(2.0, values) == 1.0


def test_percentile_rank_single_window_is_zero() -> None:
    assert percentile_rank(1.0, [1.0]) == 0.0


def test_find_local_peaks_includes_exact_threshold_only() -> None:
    windows = [
        make_window(0.80, start_ms=0),
        make_window(0.85, start_ms=10_000),
        make_window(0.70, start_ms=20_000),
    ]

    assert find_local_peaks(windows) == [windows[1]]

    below_threshold = [
        make_window(0.80, start_ms=0),
        make_window(0.849, start_ms=10_000),
        make_window(0.70, start_ms=20_000),
    ]

    assert find_local_peaks(below_threshold) == []


def test_find_local_peaks_can_select_first_window() -> None:
    windows = [
        make_window(0.90, start_ms=0),
        make_window(0.80, start_ms=10_000),
        make_window(0.70, start_ms=20_000),
    ]

    assert find_local_peaks(windows) == [windows[0]]


def test_find_local_peaks_can_select_last_window() -> None:
    windows = [
        make_window(0.70, start_ms=0),
        make_window(0.80, start_ms=10_000),
        make_window(0.90, start_ms=20_000),
    ]

    assert find_local_peaks(windows) == [windows[2]]


def test_find_local_peaks_can_select_single_window_part() -> None:
    window = make_window(0.85)

    assert find_local_peaks([window]) == [window]


def test_find_local_peaks_selects_higher_of_two_windows() -> None:
    windows = [
        make_window(0.85, start_ms=0),
        make_window(0.90, start_ms=10_000),
    ]

    assert find_local_peaks(windows) == [windows[1]]


def test_find_local_peaks_keeps_earliest_window_on_plateau() -> None:
    windows = [
        make_window(0.70, start_ms=0),
        make_window(0.90, start_ms=10_000),
        make_window(0.90, start_ms=20_000),
        make_window(0.80, start_ms=30_000),
    ]

    assert find_local_peaks(windows) == [windows[1]]


def test_stream_parts_share_normalization() -> None:
    low_part = [
        make_danmaku(
            timestamp_ms=0,
            part_id="part-low",
        )
    ]
    high_part = [
        make_danmaku(
            timestamp_ms=0,
            text=f"普通弹幕-{index}",
            part_id="part-high",
        )
        for index in range(5)
    ]

    windows = build_stream_signal_windows(
        [
            ("part-low", low_part),
            ("part-high", high_part),
        ],
        stream_id="stream-1",
    )
    by_part = {
        window.part_id: window
        for window in windows
    }

    assert by_part["part-low"].density_score == 0.0
    assert by_part["part-high"].density_score == 1.0


def test_find_local_peaks_compares_neighbors_within_each_part() -> None:
    part_one = [
        make_window(0.90, start_ms=0, part_id="part-1"),
        make_window(0.20, start_ms=10_000, part_id="part-1"),
    ]
    part_two = [
        make_window(0.10, start_ms=0, part_id="part-2"),
        make_window(0.95, start_ms=10_000, part_id="part-2"),
    ]

    peaks = find_local_peaks(part_one + part_two)

    assert peaks == [part_two[1], part_one[0]]


def test_find_local_peaks_separates_same_part_id_across_streams() -> None:
    first = make_window(
        0.90,
        stream_id="stream-1",
        part_id="shared-part",
    )
    second = make_window(
        0.95,
        stream_id="stream-2",
        part_id="shared-part",
    )

    assert find_local_peaks([first, second]) == [second, first]


def test_build_windows_for_part_allows_empty_danmaku() -> None:
    assert build_windows_for_part(
        stream_id="stream-1",
        part_id="part-1",
        danmaku=[],
    ) == []


def test_build_windows_use_half_open_time_boundaries() -> None:
    windows = build_windows_for_part(
        stream_id="stream-1",
        part_id="part-1",
        danmaku=[
            make_danmaku(0),
            make_danmaku(29_999),
            make_danmaku(30_000),
        ],
    )
    by_start = {
        window.start_ms: window
        for window in windows
    }

    assert by_start[0].danmaku_count == 2
    assert by_start[30_000].danmaku_count == 1


def test_signal_normalization_does_not_mutate_danmaku() -> None:
    danmaku = make_danmaku(
        timestamp_ms=0,
        text="？？？",
        raw_text=r"{\an8}？？？",
    )
    original_text = danmaku.text
    original_raw_text = danmaku.raw_text

    assert normalize_signal_text(danmaku.text) == "<QUESTION>"
    build_windows_for_part(
        stream_id=danmaku.stream_id,
        part_id=danmaku.part_id,
        danmaku=[danmaku],
    )

    assert danmaku.text == original_text
    assert danmaku.raw_text == original_raw_text


def test_find_peak_ms_stays_inside_candidate_window() -> None:
    candidate = make_window(0.90)
    peak_ms = find_peak_ms(
        candidate,
        [
            make_danmaku(1_000),
            make_danmaku(15_000),
            make_danmaku(29_999),
        ],
    )

    assert candidate.start_ms <= peak_ms <= candidate.end_ms


def test_find_peak_ms_returns_midpoint_for_empty_danmaku() -> None:
    candidate = make_window(0.90, start_ms=10_000)

    assert find_peak_ms(candidate, []) == 25_000
