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