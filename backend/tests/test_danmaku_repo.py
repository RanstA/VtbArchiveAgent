import sqlite3
from datetime import datetime

import pytest

from app.domain.evidence.danmaku import Danmaku
from app.domain.source.stream import Stream
from app.domain.source.stream_part import StreamPart
from app.domain.source.vtuber import Vtuber
from app.repository.danmaku_repo import (
    insert_danmaku_batch,
    list_danmaku_by_stream_part,
    list_danmaku_window,
)
from app.repository.database import init_db
from app.repository.stream_part_repo import insert_stream_part
from app.repository.stream_repo import insert_stream
from app.repository.vtuber_repo import insert_vtuber


def test_sqlite_assigns_ids_and_read_side_returns_v1_danmaku() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        init_db(connection)
        assert {
            row[1] for row in connection.execute("PRAGMA table_info(danmaku)")
        } == {"id", "stream_part_id", "timestamp_ms", "raw_text", "text"}
        insert_vtuber(connection, Vtuber(id="aza", display_name="Aza"))
        insert_stream(
            connection,
            Stream(
                id="stream-test",
                vtuber_id="aza",
                live_time=datetime(2026, 9, 20, 12, 0),
                title="测试直播",
            ),
        )
        stream_part_id = insert_stream_part(
            connection,
            StreamPart(stream_id="stream-test", part_id="p0"),
        )
        pending = [
            {
                "stream_id": "stream-test",
                "part_id": "p0",
                "timestamp_ms": 1000,
                "raw_text": r"{\c&HFFFFFF&}第一条",
                "text": "第一条",
            },
            {
                "stream_id": "stream-test",
                "part_id": "p0",
                "timestamp_ms": 2000,
                "raw_text": "第二条",
                "text": "第二条",
            },
        ]
        assert all("id" not in item for item in pending)
        insert_danmaku_batch(connection, stream_part_id, pending)

        with pytest.raises(ValueError, match="timestamp_ms"):
            insert_danmaku_batch(
                connection,
                stream_part_id,
                [{**pending[0], "timestamp_ms": -1}],
            )

        database_rows = connection.execute(
            "SELECT id, timestamp_ms, raw_text, text FROM danmaku ORDER BY id"
        ).fetchall()
        assert len(database_rows) == 2
        assert all(isinstance(row[0], int) and row[0] > 0 for row in database_rows)
        assert database_rows[0][0] != database_rows[1][0]

        stored = list_danmaku_by_stream_part(
            connection, stream_part_id, "stream-test", "p0"
        )
        assert all(isinstance(item, Danmaku) for item in stored)
        assert [item.id for item in stored] == [row[0] for row in database_rows]
        assert [(item.stream_id, item.part_id) for item in stored] == [
            ("stream-test", "p0"),
            ("stream-test", "p0"),
        ]
        assert [(item.timestamp_ms, item.raw_text, item.text) for item in stored] == [
            row[1:] for row in database_rows
        ]
        assert [row["id"] for row in list_danmaku_window(
            connection,
            stream_id="stream-test",
            part_id="p0",
            start_ms=0,
            end_ms=3000,
        )] == [item.id for item in stored]
        assert list_danmaku_by_stream_part(
            connection, stream_part_id, "another-stream", "p0"
        ) == []
    finally:
        connection.close()
