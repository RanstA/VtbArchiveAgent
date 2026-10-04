import sqlite3

from app.domain.evidence.danmaku import (
    Danmaku,
)


def insert_danmaku_batch(
    connection: sqlite3.Connection,
    stream_part_id: int,
    danmaku: list[dict[str, str | int]],
) -> None:
    if not danmaku:
        return

    if any(
        not isinstance(item["timestamp_ms"], int) or item["timestamp_ms"] < 0
        for item in danmaku
    ):
        raise ValueError("timestamp_ms must be a non-negative integer")

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
                item["timestamp_ms"],
                item["raw_text"],
                item["text"],
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
            d.id,
            d.timestamp_ms,
            d.raw_text,
            d.text
        FROM danmaku AS d
        JOIN stream_parts AS sp ON sp.id = d.stream_part_id
        WHERE d.stream_part_id = ?
          AND sp.stream_id = ?
          AND sp.part_id = ?
        ORDER BY d.timestamp_ms ASC, d.id ASC
        """,
        (
            stream_part_id,
            stream_id,
            part_id,
        ),
    ).fetchall()

    return [
        Danmaku(
            id=row[0],
            stream_id=stream_id,
            part_id=part_id,
            timestamp_ms=row[1],
            raw_text=row[2],
            text=row[3],
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
    limit: int | None = 120,
) -> list[dict]:
    """
    查询某个 Stream Part 的局部弹幕窗口。

    这是 Investigation Harness
    向更细粒度 Evidence 升级时使用的接口。

    时间仍然是 Part-local timestamp。
    """

    if start_ms < 0:
        raise ValueError("start_ms must be >= 0")

    if end_ms <= start_ms:
        raise ValueError("end_ms must be greater than start_ms")

    if limit is not None and limit < 1:
        raise ValueError("limit must be >= 1")

    sql = """
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
        """

    params = [stream_id, part_id, start_ms, end_ms]

    if limit is not None:
        sql += "\nLIMIT ?"
        params.append(limit)

    rows = connection.execute(sql, params).fetchall()
