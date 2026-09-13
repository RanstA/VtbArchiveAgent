import sqlite3

from app.domain.highlight import Highlight


def replace_highlights_for_stream(
    connection: sqlite3.Connection,
    stream_id: str,
    highlights: list[Highlight],
) -> None:
    """
    用最新 detector 结果替换某场 Stream
    当前保存的全部 Highlights。

    整个过程位于同一事务：

        DELETE old
        +
        INSERT new

    如果 INSERT 过程中失败，
    DELETE 也会一起 rollback。

    因此不会出现：

        旧数据删掉了
        新数据只写了一半

    的状态。
    """

    # 防止调用方误把其他 Stream 的 Highlight
    # 混进当前批次。
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

    # sqlite3 connection context manager：
    #
    # 正常结束 -> commit
    # 发生异常 -> rollback
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
    """
    查询某场 Stream 当前保存的所有 Highlight。

    当前返回顺序：

        part_id
        ->
        Part 内 start_ms

    后面做正式 Timeline 时，
    再统一处理 p0 / p1 / p2
    拼接后的全局时间。
    """

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
    """
    根据稳定 Highlight ID
    查询单个高光。
    """

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


def _row_to_highlight(
    row: tuple,
) -> Highlight:
    """
    SQLite row -> Highlight domain model。
    """

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