import sqlite3

import pytest

from app.domain.vtuber import (
    Vtuber,
    VtuberSource,
)
from app.repository.database import (
    init_db,
)
from app.repository.vtuber_repo import (
    get_vtuber,
    insert_vtuber,
    insert_vtuber_source,
    list_vtuber_sources,
    list_vtubers,
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


def test_vtuber_and_source_round_trip():
    connection = make_connection()

    try:
        vtuber = Vtuber(
            id="aza",
            display_name="阿萨Aza",
        )

        source = VtuberSource(
            vtuber_id="aza",
            source="bilibili",
            external_id="480680646",
            display_name="阿萨Aza",
        )

        insert_vtuber(
            connection=connection,
            vtuber=vtuber,
        )

        insert_vtuber_source(
            connection=connection,
            vtuber_source=source,
        )

        stored = get_vtuber(
            connection=connection,
            vtuber_id="aza",
        )

        assert stored == vtuber

        sources = list_vtuber_sources(
            connection=connection,
            vtuber_id="aza",
        )

        assert sources == [
            source
        ]

        assert list_vtubers(
            connection
        ) == [
            vtuber
        ]

    finally:
        connection.close()


def test_vtuber_and_source_can_be_updated():
    connection = make_connection()

    try:
        insert_vtuber(
            connection=connection,
            vtuber=Vtuber(
                id="mikoto",
                display_name="旧名字",
            ),
        )

        insert_vtuber_source(
            connection=connection,
            vtuber_source=VtuberSource(
                vtuber_id="mikoto",
                source="bilibili",
                external_id="100",
                display_name="旧平台名字",
            ),
        )

        insert_vtuber(
            connection=connection,
            vtuber=Vtuber(
                id="mikoto",
                display_name="蜜言Mikoto",
            ),
        )

        insert_vtuber_source(
            connection=connection,
            vtuber_source=VtuberSource(
                vtuber_id="mikoto",
                source="bilibili",
                external_id="200",
                display_name="蜜言Mikoto",
            ),
        )

        stored = get_vtuber(
            connection=connection,
            vtuber_id="mikoto",
        )

        assert stored is not None

        assert (
            stored.display_name
            == "蜜言Mikoto"
        )

        sources = list_vtuber_sources(
            connection=connection,
            vtuber_id="mikoto",
        )

        assert len(
            sources
        ) == 1

        assert (
            sources[0].external_id
            == "200"
        )

        assert (
            sources[0].display_name
            == "蜜言Mikoto"
        )

    finally:
        connection.close()


def test_same_external_identity_cannot_belong_to_two_vtubers():
    connection = make_connection()

    try:
        first = Vtuber(
            id="vtuber-a",
            display_name="主播 A",
        )

        second = Vtuber(
            id="vtuber-b",
            display_name="主播 B",
        )

        insert_vtuber(
            connection=connection,
            vtuber=first,
        )

        insert_vtuber(
            connection=connection,
            vtuber=second,
        )

        insert_vtuber_source(
            connection=connection,
            vtuber_source=VtuberSource(
                vtuber_id=first.id,
                source="bilibili",
                external_id="123456",
                display_name="主播 A",
            ),
        )

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            insert_vtuber_source(
                connection=connection,
                vtuber_source=VtuberSource(
                    vtuber_id=second.id,
                    source="bilibili",
                    external_id="123456",
                    display_name="主播 B",
                ),
            )

    finally:
        connection.close()