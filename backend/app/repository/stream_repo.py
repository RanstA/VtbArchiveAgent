import json
import sqlite3

from app.domain.stream import Stream


def insert_stream(
    connection: sqlite3.Connection,
    stream: Stream,
) -> None:
    connection.execute(
        """
        INSERT INTO streams (
            id,
            month,
            live_time,
            publish_times,
            title,
            video_url,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(id)
        DO UPDATE SET
            month = excluded.month,
            live_time = excluded.live_time,
            publish_times = excluded.publish_times,
            title = excluded.title,
            video_url = excluded.video_url,
            status = excluded.status
        """,
        (
            stream.id,
            stream.month,
            stream.live_time.isoformat(),
            json.dumps(
                [
                    time.isoformat()
                    for time in stream.publish_times
                ],
                ensure_ascii=False,
            ),
            stream.title,
            stream.video_url,
            stream.status,
        ),
    )

    # 当前 Stream 的 BV 关系重新同步
    connection.execute(
        """
        DELETE FROM stream_bv_ids
        WHERE stream_id = ?
        """,
        (stream.id,),
    )

    connection.executemany(
        """
        INSERT INTO stream_bv_ids (
            stream_id,
            bv_id
        )
        VALUES (?, ?)
        """,
        [
            (
                stream.id,
                bv_id,
            )
            for bv_id in stream.bv_ids
        ],
    )
    
def list_streams(
    connection: sqlite3.Connection,
    query: str | None = None,
) -> list[dict]:
    query_pattern = (
        f"%{query_strip()}%"
        if query and query.strip()
        else None
    )
    
    rows = connection.execute(
        """
        
        SELECT
            s.id,
            s.title,
            s.live_time,
            s.status,
            
            (
                SELECT GROUP_CONCAT(b.bv_id)
                FROM stream_bv_ids AS b
                WHERE b.stream_id = s.id
            ) AS bv_ids,
            
            EXISTS (
                SELECT 1
                FROM stream_parts AS sp
                JOIN danmaku AS d
                    ON d.stream_part_id = sp.id
                WHERE sp.stream_id = s.id
                LIMIT 1
            ) AS has_danmaku
            
         FROM streams AS s

        WHERE (
            ? IS NULL

            OR s.title LIKE ?

            OR EXISTS (
                SELECT 1
                FROM stream_bv_ids AS b
                WHERE
                    b.stream_id = s.id
                    AND b.bv_id LIKE ?
            )
        )
        
        ORDER BY s.live_time DESC
        
        """,
        (
            query_pattern,
            query_pattern,
            query_pattern,
        )
        
    ).fetchall()
    
    result = []
    
    for row in rows:
        result.append(
            {
                "id": row[0],
                "title": row[1],
                "live_time": row[2],
                "status": row[3],
                "bv_ids": (
                    row[4].split(",")
                    if row[4]
                    else []
                ),
                "has_danmaku": bool(row[5]),
            }
        )
        
    return result