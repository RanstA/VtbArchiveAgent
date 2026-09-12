import sqlite3

from app.domain.danmaku import Danmaku


def insert_danmaku_batch(
    connection: sqlite3.Connection,
    stream_part_id: int,
    danmaku: list[Danmaku],
) -> None:
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