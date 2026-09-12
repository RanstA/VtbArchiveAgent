import sqlite3

from app.domain.danmaku import Danmaku


def insert_danmaku_batch(
    connection: sqlite3.Connection,
    stream_part_id: int,
    danmaku: list[Danmaku],
) -> None:
    
    if not danmaku: return
    
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
    part_id: str
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
        (stream_part_id,),
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