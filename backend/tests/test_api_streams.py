from datetime import (
    datetime,
)
from pathlib import Path

from fastapi.testclient import (
    TestClient,
)

from app.config.settings import (
    settings,
)
from app.domain.stream import (
    Stream,
    make_stream_id,
)
from app.domain.vtuber import (
    Vtuber,
)
from app.main import app
from app.repository.database import (
    connect_db,
    init_db,
)
from app.repository.stream_repo import (
    insert_stream,
)
from app.repository.vtuber_repo import (
    insert_vtuber,
)


client = TestClient(
    app
)


def make_stream(
    *,
    vtuber_id: str,
    title: str,
    minute: int,
) -> Stream:
    live_time = datetime(
        2026,
        9,
        20,
        12,
        minute,
    )

    return Stream(
        id=make_stream_id(
            vtuber_id=(
                vtuber_id
            ),
            live_time=live_time,
            title=title,
        ),
        vtuber_id=vtuber_id,
        month="2026-09",
        live_time=live_time,
        publish_times=[],
        bv_ids=[
            (
                "BV-MIKOTO"
                if (
                    vtuber_id
                    == "mikoto"
                )
                else "BV-AZA"
            )
        ],
        title=title,
        video_url="",
        status="online",
    )


def prepare_database(
    db_path: Path,
) -> tuple[
    Stream,
    Stream,
]:
    connection = connect_db(
        db_path
    )

    try:
        init_db(
            connection
        )

        with connection:
            insert_vtuber(
                connection=connection,
                vtuber=Vtuber(
                    id="mikoto",
                    display_name="蜜言",
                ),
            )

            insert_vtuber(
                connection=connection,
                vtuber=Vtuber(
                    id="aza",
                    display_name="阿萨Aza",
                ),
            )

            mikoto_stream = (
                make_stream(
                    vtuber_id=(
                        "mikoto"
                    ),
                    title=(
                        "蜜言测试直播"
                    ),
                    minute=0,
                )
            )

            aza_stream = (
                make_stream(
                    vtuber_id="aza",
                    title=(
                        "Aza测试直播"
                    ),
                    minute=10,
                )
            )

            insert_stream(
                connection=connection,
                stream=(
                    mikoto_stream
                ),
            )

            insert_stream(
                connection=connection,
                stream=(
                    aza_stream
                ),
            )

        return (
            mikoto_stream,
            aza_stream,
        )

    finally:
        connection.close()


def test_get_streams_returns_vtuber_identity(
    tmp_path: Path,
    monkeypatch,
):
    db_path = (
        tmp_path
        / "api.db"
    )

    prepare_database(
        db_path
    )

    monkeypatch.setattr(
        settings,
        "database_path",
        db_path,
    )

    response = client.get(
        "/streams"
    )

    assert (
        response.status_code
        == 200
    )

    payload = (
        response.json()
    )

    assert len(
        payload
    ) == 2

    by_vtuber = {
        item["vtuberId"]: item
        for item in payload
    }

    assert (
        by_vtuber[
            "mikoto"
        ][
            "vtuberName"
        ]
        == "蜜言"
    )

    assert (
        by_vtuber[
            "aza"
        ][
            "vtuberName"
        ]
        == "阿萨Aza"
    )


def test_get_streams_can_filter_by_vtuber(
    tmp_path: Path,
    monkeypatch,
):
    db_path = (
        tmp_path
        / "api.db"
    )

    (
        mikoto_stream,
        _,
    ) = prepare_database(
        db_path
    )

    monkeypatch.setattr(
        settings,
        "database_path",
        db_path,
    )

    response = client.get(
        "/streams",
        params={
            "vtuber_id": (
                "mikoto"
            ),
        },
    )

    assert (
        response.status_code
        == 200
    )

    payload = (
        response.json()
    )

    assert len(
        payload
    ) == 1

    assert (
        payload[0]["id"]
        == mikoto_stream.id
    )

    assert (
        payload[0][
            "vtuberId"
        ]
        == "mikoto"
    )

    assert (
        payload[0][
            "vtuberName"
        ]
        == "蜜言"
    )


def test_unknown_vtuber_returns_empty_stream_list(
    tmp_path: Path,
    monkeypatch,
):
    db_path = (
        tmp_path
        / "api.db"
    )

    prepare_database(
        db_path
    )

    monkeypatch.setattr(
        settings,
        "database_path",
        db_path,
    )

    response = client.get(
        "/streams",
        params={
            "vtuber_id": (
                "unknown"
            ),
        },
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        response.json()
        == []
    )
    
    
def test_blank_vtuber_id_is_rejected(
    tmp_path: Path,
    monkeypatch,
):
    db_path = (
        tmp_path
        / "api.db"
    )

    prepare_database(
        db_path
    )

    monkeypatch.setattr(
        settings,
        "database_path",
        db_path,
    )

    response = client.get(
        "/streams",
        params={
            "vtuber_id": "   ",
        },
    )

    assert (
        response.status_code
        == 422
    )