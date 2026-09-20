from pathlib import Path

from fastapi.testclient import (
    TestClient,
)

from app.config.settings import (
    settings,
)
from app.domain.vtuber import (
    Vtuber,
)
from app.main import app
from app.repository.database import (
    connect_db,
    init_db,
)
from app.repository.vtuber_repo import (
    insert_vtuber,
)


client = TestClient(
    app
)


def prepare_database(
    db_path: Path,
) -> None:
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
                    display_name="蜜言Mikoto",
                ),
            )

            insert_vtuber(
                connection=connection,
                vtuber=Vtuber(
                    id="aza",
                    display_name="阿萨Aza",
                ),
            )

    finally:
        connection.close()


def test_get_vtubers(
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
        "/vtubers"
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

    assert {
        item["id"]: (
            item["displayName"]
        )
        for item in payload
    } == {
        "mikoto": "蜜言Mikoto",
        "aza": "阿萨Aza",
    }