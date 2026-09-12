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


def delete_stream_parts(
    connection: sqlite3.Connection,
    stream_id: str,
) -> None:
    """
    删除某场 Stream 的所有 Part。

    因为数据库启用了 ON DELETE CASCADE，
    对应的 danmaku 也会一起被删除。

    这样重新导入一场 Stream 时不会产生重复弹幕。
    """
    connection.execute(
        """
        DELETE FROM stream_parts
        WHERE stream_id = ?
        """,
        (stream_id,),
    )
