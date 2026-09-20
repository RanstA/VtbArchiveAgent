import sqlite3

from app.domain.danmaku import (
    Danmaku,
)
from app.domain.highlight import (
    Highlight,
    make_highlight_id,
)
from app.event_pipeline.signals import (
    build_stream_signal_windows,
    find_local_peaks,
    find_peak_ms,
)
from app.repository.danmaku_repo import (
    list_danmaku_by_stream_part,
)
from app.repository.highlight_repo import (
    replace_highlights_for_stream,
)
from app.repository.stream_part_repo import (
    list_stream_parts,
)


DEFAULT_MIN_SCORE = 0.85
DETECTOR_VERSION = "v0.1"


def generate_highlights_for_stream(
    connection: sqlite3.Connection,
    stream_id: str,
    *,
    min_score: float = DEFAULT_MIN_SCORE,
    detector_version: str = DETECTOR_VERSION,
) -> list[Highlight]:
    """
    从 SQLite 中已有的 Danmaku
    为一场 Stream 生成 Highlight，
    并替换数据库中的旧检测结果。

    Pipeline:

        StreamPart
        -> Danmaku
        -> SignalWindow
        -> Local Peak
        -> Highlight
        -> SQLite

    注意：

    这里的 peak_ms 表示：

        当前 Highlight 中
        观众反应最强的时间锚点。

    它不是主播内容精确发生的时间。
    """

    stream_id = (
        stream_id.strip()
    )

    detector_version = (
        detector_version.strip()
    )

    if not stream_id:
        raise ValueError(
            "stream_id cannot be empty"
        )

    if not (
        0.0
        <= min_score
        <= 1.0
    ):
        raise ValueError(
            "min_score must be between "
            "0.0 and 1.0"
        )

    if not detector_version:
        raise ValueError(
            "detector_version "
            "cannot be empty"
        )

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

        danmaku_by_part[
            part_id
        ] = danmaku

        stream_parts.append(
            (
                part_id,
                danmaku,
            )
        )

    windows = (
        build_stream_signal_windows(
            stream_parts=stream_parts,
            stream_id=stream_id,
        )
    )

    peaks = find_local_peaks(
        windows=windows,
        min_score=min_score,
    )

    highlights: list[
        Highlight
    ] = []

    for peak in peaks:
        part_danmaku = (
            danmaku_by_part.get(
                peak.part_id,
                [],
            )
        )

        peak_ms = find_peak_ms(
            peak_window=peak,
            danmaku=part_danmaku,
        )

        highlight = Highlight(
            id=make_highlight_id(
                stream_id=(
                    peak.stream_id
                ),
                part_id=(
                    peak.part_id
                ),
                start_ms=(
                    peak.start_ms
                ),
                end_ms=(
                    peak.end_ms
                ),
            ),
            stream_id=(
                peak.stream_id
            ),
            part_id=(
                peak.part_id
            ),
            start_ms=(
                peak.start_ms
            ),
            end_ms=(
                peak.end_ms
            ),
            peak_ms=peak_ms,
            score=peak.score,
            density_score=(
                peak.density_score
            ),
            repetition_score=(
                peak.repetition_score
            ),
            reaction_score=(
                peak.reaction_score
            ),
            danmaku_count=(
                peak.danmaku_count
            ),
            unique_text_count=(
                peak.unique_text_count
            ),
            repetition_ratio=(
                peak.repetition_ratio
            ),
            reaction_ratio=(
                peak.reaction_ratio
            ),
            laugh_count=(
                peak.laugh_count
            ),
            question_count=(
                peak.question_count
            ),
            exclamation_count=(
                peak.exclamation_count
            ),
            detector_version=(
                detector_version
            ),
        )

        highlights.append(
            highlight
        )

    replace_highlights_for_stream(
        connection=connection,
        stream_id=stream_id,
        highlights=highlights,
    )

    return highlights