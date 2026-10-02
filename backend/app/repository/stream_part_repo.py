import sqlite3

from app.domain.source.stream_part import StreamPart


def insert_stream_part(
    connection: sqlite3.Connection,
    part: StreamPart,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO stream_parts (
            stream_id,
            part_id,
            start_offset_ms,
            bvid,
            cid,
            page,
            duration_ms,
            video_path,
            danmaku_path,
            xml_path
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            part.stream_id,
            part.part_id,
            part.start_offset_ms,
            part.bvid,
            part.cid,
            part.page,
            part.duration_ms,
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
    对应的 danmaku / highlights 也会一起被删除。

    这样重新导入一场 Stream 时不会产生重复派生数据。
    """

    connection.execute(
        """
        DELETE FROM stream_parts
        WHERE stream_id = ?
        """,
        (stream_id,),
    )


def list_stream_parts(
    connection: sqlite3.Connection,
    stream_id: str,
) -> list[dict]:
    rows = connection.execute(
        """
        SELECT
            id,
            part_id,
            start_offset_ms,
            bvid,
            cid,
            page,
            duration_ms,
            video_path,
            danmaku_path,
            xml_path
        FROM stream_parts
        WHERE stream_id = ?
        ORDER BY id ASC
        """,
        (stream_id,),
    ).fetchall()

    return [
        {
            "id": row[0],
            "part_id": row[1],
            "start_offset_ms": row[2],
            "bvid": row[3],
            "cid": row[4],
            "page": row[5],
            "duration_ms": row[6],
            "video_path": row[7],
            "danmaku_path": row[8],
            "xml_path": row[9],
        }
        for row in rows
    ]
