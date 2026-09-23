import sqlite3

from app.domain.danmaku import (
    Danmaku,
)


def insert_danmaku_batch(
    connection: sqlite3.Connection,
    stream_part_id: int,
    danmaku: list[Danmaku],
) -> None:
    if not danmaku:
        return

    connection.executemany(
        """
        INSERT INTO danmaku (
            stream_part_id,
            timestamp_ms,
            raw_text,
            text
        )
        VALUES (?, ?, ?, ?)
        """,
        [
            (
                stream_part_id,
                item.timestamp_ms,
                item.raw_text,
                item.text,
            )
            for item in danmaku
        ],
    )


def list_danmaku_by_stream_part(
    connection: sqlite3.Connection,
    stream_part_id: int,
    stream_id: str,
    part_id: str,
) -> list[Danmaku]:
    rows = connection.execute(
        """
        SELECT
            timestamp_ms,
            raw_text,
            text
        FROM danmaku
        WHERE stream_part_id = ?
        ORDER BY timestamp_ms ASC
        """,
        (
            stream_part_id,
        ),
    ).fetchall()

    return [
        Danmaku(
            stream_id=stream_id,
            part_id=part_id,
            timestamp_ms=row[0],
            raw_text=row[1],
            text=row[2],
        )
        for row in rows
    ]


def list_danmaku_window(
    connection: sqlite3.Connection,
    *,
    stream_id: str,
    part_id: str,
    start_ms: int,
    end_ms: int,
    limit: int = 120,
) -> list[dict]:
    """
    查询某个 Stream Part 的局部弹幕窗口。

    这是 Investigation Harness
    向更细粒度 Evidence 升级时使用的接口。

    时间仍然是 Part-local timestamp。
    """

    if start_ms < 0:
        raise ValueError(
            "start_ms must be >= 0"
        )

    if end_ms <= start_ms:
        raise ValueError(
            "end_ms must be greater than start_ms"
        )

    if limit < 1:
        raise ValueError(
            "limit must be >= 1"
        )

    rows = connection.execute(
        """
        SELECT
            d.id,
            d.timestamp_ms,
            d.raw_text,
            d.text

        FROM danmaku AS d

        JOIN stream_parts AS sp
            ON sp.id = d.stream_part_id

        WHERE
            sp.stream_id = ?
            AND sp.part_id = ?
            AND d.timestamp_ms >= ?
            AND d.timestamp_ms < ?

        ORDER BY
            d.timestamp_ms ASC,
            d.id ASC

        LIMIT ?
        """,
        (
            stream_id,
            part_id,
            start_ms,
            end_ms,
            limit,
        ),
    ).fetchall()

    return [
        {
            "id": int(
                row[0]
            ),
            "timestamp_ms": int(
                row[1]
            ),
            "raw_text": row[2],
            "text": row[3],
        }
        for row in rows
    ]