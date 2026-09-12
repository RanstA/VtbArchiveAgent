import json
import sqlite3

from app.domain.stream import Stream


def insert_stream(
    connection: sqlite3.Connection,
    stream: Stream,
) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO streams (
            id,
            month,
            live_time,
            publish_times,
            bv_id,
            title,
            video_url,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            stream.id,
            stream.month,
            stream.live_time.isoformat(),
            json.dumps(
                [t.isoformat() for t in stream.publish_times],
                ensure_ascii=False,
            ),
            stream.bv_id,
            stream.title,
            stream.video_url,
            stream.status,
        ),
    )