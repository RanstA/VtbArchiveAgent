import sqlite3

import pytest

from app.domain.source.vtuber import Vtuber
from app.repository.database import init_db
from app.repository.vtuber_repo import get_vtuber, insert_vtuber, list_vtubers


def make_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    init_db(connection)
    return connection


def test_vtuber_round_trip_and_update() -> None:
    connection = make_connection()
    try:
        vtuber = Vtuber(id="aza", display_name="阿萨Aza")
        insert_vtuber(connection, vtuber)
        assert get_vtuber(connection, "aza") == vtuber
        assert list_vtubers(connection) == [vtuber]

        updated = Vtuber(id="aza", display_name="新名称")
        insert_vtuber(connection, updated)
        assert get_vtuber(connection, "aza") == updated
        assert list_vtubers(connection) == [updated]
    finally:
        connection.close()


def test_v1_schema_has_no_vtuber_sources() -> None:
    connection = make_connection()
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "vtuber_sources" not in tables
        assert "stream_bv_ids" not in tables
        assert {
            row[1] for row in connection.execute("PRAGMA table_info(streams)")
        } == {"id", "vtuber_id", "live_time", "title", "status"}
        assert {"bvid", "cid", "page", "start_offset_ms", "duration_ms",
                "video_path", "danmaku_path", "xml_path"} <= {
            row[1] for row in connection.execute("PRAGMA table_info(stream_parts)")
        }
    finally:
        connection.close()


def test_init_db_rejects_legacy_source_tables() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE TABLE vtuber_sources (id TEXT)")
        with pytest.raises(RuntimeError, match="Legacy Source tables"):
            init_db(connection)
    finally:
        connection.close()
