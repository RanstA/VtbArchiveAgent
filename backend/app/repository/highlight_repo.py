import sqlite3

from app.domain.highlight import (
    Highlight,
)


def replace_highlights_for_stream(
    connection: sqlite3.Connection,
    stream_id: str,
    highlights: list[Highlight],
) -> None:
    """
    用最新 detector 结果替换某场 Stream
    当前保存的全部 Highlights。
    """

    for highlight in highlights:
        if (
            highlight.stream_id
            != stream_id
        ):
            raise ValueError(
                "all highlights must belong "
                "to the target stream"
            )

    rows = [
        (
            highlight.id,
            highlight.stream_id,
            highlight.part_id,
            highlight.start_ms,
            highlight.end_ms,
            highlight.peak_ms,
            highlight.score,
            highlight.density_score,
            highlight.repetition_score,
            highlight.reaction_score,
            highlight.danmaku_count,
            highlight.unique_text_count,
            highlight.repetition_ratio,
            highlight.reaction_ratio,
            highlight.laugh_count,
            highlight.question_count,
            highlight.exclamation_count,
            highlight.detector_version,
        )
        for highlight in highlights
    ]

    with connection:
        connection.execute(
            """
            DELETE FROM highlights
            WHERE stream_id = ?
            """,
            (
                stream_id,
            ),
        )

        connection.executemany(
            """
            INSERT INTO highlights (
                id,
                stream_id,
                part_id,

                start_ms,
                end_ms,
                peak_ms,

                score,

                density_score,
                repetition_score,
                reaction_score,

                danmaku_count,
                unique_text_count,

                repetition_ratio,
                reaction_ratio,

                laugh_count,
                question_count,
                exclamation_count,

                detector_version
            )
            VALUES (
                ?, ?, ?,
                ?, ?, ?,
                ?,
                ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?, ?,
                ?
            )
            """,
            rows,
        )


def list_highlights_by_stream(
    connection: sqlite3.Connection,
    stream_id: str,
) -> list[Highlight]:
    rows = connection.execute(
        """
        SELECT
            id,
            stream_id,
            part_id,

            start_ms,
            end_ms,
            peak_ms,

            score,

            density_score,
            repetition_score,
            reaction_score,

            danmaku_count,
            unique_text_count,

            repetition_ratio,
            reaction_ratio,

            laugh_count,
            question_count,
            exclamation_count,

            detector_version

        FROM highlights

        WHERE stream_id = ?

        ORDER BY
            part_id ASC,
            start_ms ASC
        """,
        (
            stream_id,
        ),
    ).fetchall()

    return [
        _row_to_highlight(
            row
        )
        for row in rows
    ]


def get_highlight_by_id(
    connection: sqlite3.Connection,
    highlight_id: str,
) -> Highlight | None:
    row = connection.execute(
        """
        SELECT
            id,
            stream_id,
            part_id,

            start_ms,
            end_ms,
            peak_ms,

            score,

            density_score,
            repetition_score,
            reaction_score,

            danmaku_count,
            unique_text_count,

            repetition_ratio,
            reaction_ratio,

            laugh_count,
            question_count,
            exclamation_count,

            detector_version

        FROM highlights

        WHERE id = ?
        """,
        (
            highlight_id,
        ),
    ).fetchone()

    if row is None:
        return None

    return _row_to_highlight(
        row
    )


def search_highlights_for_vtuber(
    connection: sqlite3.Connection,
    *,
    vtuber_id: str,
    limit: int = 8,
    min_score: float = 0.85,
) -> list[dict]:
    """
    Event Scout 的 coarse retrieval。

    Highlight 是观众反应候选，
    这里只根据 detector signal
    做第一阶段召回。
    """

    if limit < 1:
        raise ValueError(
            "limit must be >= 1"
        )

    if not (
        0.0
        <= min_score
        <= 1.0
    ):
        raise ValueError(
            "min_score must be between 0 and 1"
        )

    rows = connection.execute(
        """
        SELECT
            h.id,
            h.stream_id,
            h.part_id,

            h.start_ms,
            h.end_ms,
            h.peak_ms,

            h.score,

            h.density_score,
            h.repetition_score,
            h.reaction_score,

            h.danmaku_count,
            h.unique_text_count,

            h.repetition_ratio,
            h.reaction_ratio,

            h.laugh_count,
            h.question_count,
            h.exclamation_count,

            h.detector_version,

            s.title,
            s.live_time,
            v.display_name

        FROM highlights AS h

        JOIN streams AS s
            ON s.id = h.stream_id

        JOIN vtubers AS v
            ON v.id = s.vtuber_id

        WHERE
            s.vtuber_id = ?
            AND h.score >= ?

        ORDER BY
            h.score DESC,
            s.live_time DESC

        LIMIT ?
        """,
        (
            vtuber_id,
            min_score,
            limit,
        ),
    ).fetchall()

    results: list[
        dict
    ] = []

    for row in rows:
        highlight = (
            _row_to_highlight(
                row[:18]
            )
        )

        results.append(
            {
                "highlight": highlight,
                "stream_title": row[18],
                "live_time": row[19],
                "vtuber_name": row[20],
            }
        )

    return results


def _row_to_highlight(
    row: tuple,
) -> Highlight:
    return Highlight(
        id=row[0],
        stream_id=row[1],
        part_id=row[2],

        start_ms=row[3],
        end_ms=row[4],
        peak_ms=row[5],

        score=row[6],

        density_score=row[7],
        repetition_score=row[8],
        reaction_score=row[9],

        danmaku_count=row[10],
        unique_text_count=row[11],

        repetition_ratio=row[12],
        reaction_ratio=row[13],

        laugh_count=row[14],
        question_count=row[15],
        exclamation_count=row[16],

        detector_version=row[17],
    )