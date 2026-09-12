import sqlite3

from app.domain.stream_part import StreamPart


def insert_stream_part(
    connection: sqlite3.Connection,
    part: StreamPart,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO stream_parts (
            stream_id,
            part_id,
            video_path,
            danmaku_path,
            xml_path
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            part.stream_id,
            part.part_id,
            part.video_path,
            part.danmaku_path,
            part.xml_path,
        ),
    )

    return cursor.lastrowid