import json
import sqlite3

from app.domain.stream import (
    Stream,
)


def insert_stream(
    connection: sqlite3.Connection,
    stream: Stream,
) -> None:
    connection.execute(
        """
        INSERT INTO streams (
            id,
            vtuber_id,
            month,
            live_time,
            publish_times,
            title,
            video_url,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(id)
        DO UPDATE SET
            vtuber_id = excluded.vtuber_id,
            month = excluded.month,
            live_time = excluded.live_time,
            publish_times = excluded.publish_times,
            title = excluded.title,
            video_url = excluded.video_url,
            status = excluded.status
        """,
        (
            stream.id,
            stream.vtuber_id,
            stream.month,
            stream.live_time.isoformat(),
            json.dumps(
                [
                    time.isoformat()
                    for time
                    in stream.publish_times
                ],
                ensure_ascii=False,
            ),
            stream.title,
            stream.video_url,
            stream.status,
        ),
    )

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
            for bv_id
            in stream.bv_ids
        ],
    )


def _row_to_stream_dict(
    row: tuple,
) -> dict:
    return {
        "id": row[0],
        "vtuber_id": row[1],
        "vtuber_name": row[2],
        "title": row[3],
        "live_time": row[4],
        "status": row[5],
        "bv_ids": (
            row[6].split(",")
            if row[6]
            else []
        ),
        "has_danmaku": bool(
            row[7]
        ),
        "highlight_count": int(
            row[8]
        ),
    }


def list_streams(
    connection: sqlite3.Connection,
    query: str | None = None,
    vtuber_id: str | None = None,
) -> list[dict]:
    query_pattern = (
        f"%{query.strip()}%"
        if query
        and query.strip()
        else None
    )

    vtuber_filter = (
        vtuber_id.strip()
        if vtuber_id
        and vtuber_id.strip()
        else None
    )

    rows = connection.execute(
        """
        SELECT
            s.id,
            s.vtuber_id,
            v.display_name,
            s.title,
            s.live_time,
            s.status,

            (
                SELECT GROUP_CONCAT(
                    b.bv_id
                )
                FROM stream_bv_ids AS b
                WHERE
                    b.stream_id = s.id
            ) AS bv_ids,

            EXISTS (
                SELECT 1
                FROM stream_parts AS sp

                JOIN danmaku AS d
                    ON d.stream_part_id
                    = sp.id

                WHERE
                    sp.stream_id = s.id

                LIMIT 1
            ) AS has_danmaku,

            (
                SELECT COUNT(*)
                FROM highlights AS h
                WHERE
                    h.stream_id = s.id
            ) AS highlight_count

        FROM streams AS s

        JOIN vtubers AS v
            ON v.id = s.vtuber_id

        WHERE (
            ? IS NULL
            OR s.vtuber_id = ?
        )

        AND (
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

        ORDER BY
            s.live_time DESC
        """,
        (
            vtuber_filter,
            vtuber_filter,
            query_pattern,
            query_pattern,
            query_pattern,
        ),
    ).fetchall()

    return [
        _row_to_stream_dict(
            row
        )
        for row in rows
    ]


def get_stream_by_id(
    connection: sqlite3.Connection,
    stream_id: str,
) -> dict | None:
    normalized_stream_id = (
        stream_id.strip()
    )

    if not normalized_stream_id:
        return None

    row = connection.execute(
        """
        SELECT
            s.id,
            s.vtuber_id,
            v.display_name,
            s.title,
            s.live_time,
            s.status,

            (
                SELECT GROUP_CONCAT(
                    b.bv_id
                )
                FROM stream_bv_ids AS b
                WHERE
                    b.stream_id = s.id
            ) AS bv_ids,

            EXISTS (
                SELECT 1
                FROM stream_parts AS sp

                JOIN danmaku AS d
                    ON d.stream_part_id
                    = sp.id

                WHERE
                    sp.stream_id = s.id

                LIMIT 1
            ) AS has_danmaku,

            (
                SELECT COUNT(*)
                FROM highlights AS h
                WHERE
                    h.stream_id = s.id
            ) AS highlight_count

        FROM streams AS s

        JOIN vtubers AS v
            ON v.id = s.vtuber_id

        WHERE
            s.id = ?

        LIMIT 1
        """,
        (
            normalized_stream_id,
        ),
    ).fetchone()

    if row is None:
        return None

    return _row_to_stream_dict(
        row
    )