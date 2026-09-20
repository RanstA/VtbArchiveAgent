import sqlite3
from datetime import datetime

import pytest

from app.domain.stream import (
    Stream,
    make_stream_id,
)
from app.domain.vtuber import (
    Vtuber,
)
from app.repository.database import (
    init_db,
)
from app.repository.stream_repo import (
    insert_stream,
    list_streams,
)
from app.repository.vtuber_repo import (
    insert_vtuber,
)


def make_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(
        ":memory:"
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    init_db(
        connection
    )

    return connection


def make_stream(
    *,
    vtuber_id: str,
    title: str = "测试直播",
    live_time: datetime | None = None,
) -> Stream:
    if live_time is None:
        live_time = datetime(
            2026,
            9,
            20,
            12,
            0,
        )

    return Stream(
        id=make_stream_id(
            vtuber_id=vtuber_id,
            live_time=live_time,
            title=title,
        ),
        vtuber_id=vtuber_id,
        month="2026-09",
        live_time=live_time,
        publish_times=[],
        bv_ids=[
            "BV1TEST"
        ],
        title=title,
        video_url=(
            "https://www.bilibili.com/"
            "video/BV1TEST"
        ),
        status="online",
    )


def test_stream_round_trip_contains_vtuber_information():
    connection = make_connection()

    try:
        vtuber = Vtuber(
            id="aza",
            display_name="阿萨Aza",
        )

        insert_vtuber(
            connection=connection,
            vtuber=vtuber,
        )

        stream = make_stream(
            vtuber_id=vtuber.id,
        )

        insert_stream(
            connection=connection,
            stream=stream,
        )

        rows = list_streams(
            connection=connection,
        )

        assert len(
            rows
        ) == 1

        row = rows[0]

        assert (
            row["id"]
            == stream.id
        )

        assert (
            row["vtuber_id"]
            == "aza"
        )

        assert (
            row["vtuber_name"]
            == "阿萨Aza"
        )

        assert (
            row["bv_ids"]
            == ["BV1TEST"]
        )

    finally:
        connection.close()


def test_list_streams_can_filter_by_vtuber():
    connection = make_connection()

    try:
        first_vtuber = Vtuber(
            id="vtuber-a",
            display_name="主播 A",
        )

        second_vtuber = Vtuber(
            id="vtuber-b",
            display_name="主播 B",
        )

        insert_vtuber(
            connection=connection,
            vtuber=first_vtuber,
        )

        insert_vtuber(
            connection=connection,
            vtuber=second_vtuber,
        )

        first_stream = make_stream(
            vtuber_id=first_vtuber.id,
            title="同名直播",
        )

        second_stream = make_stream(
            vtuber_id=second_vtuber.id,
            title="同名直播",
        )

        insert_stream(
            connection=connection,
            stream=first_stream,
        )

        insert_stream(
            connection=connection,
            stream=second_stream,
        )

        rows = list_streams(
            connection=connection,
            vtuber_id="vtuber-a",
        )

        assert len(
            rows
        ) == 1

        assert (
            rows[0]["vtuber_id"]
            == "vtuber-a"
        )

        assert (
            rows[0]["id"]
            == first_stream.id
        )

        assert (
            first_stream.id
            != second_stream.id
        )

    finally:
        connection.close()


def test_stream_requires_existing_vtuber():
    connection = make_connection()

    try:
        stream = make_stream(
            vtuber_id="missing-vtuber",
        )

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            insert_stream(
                connection=connection,
                stream=stream,
            )

    finally:
        connection.close()