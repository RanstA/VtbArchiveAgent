import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

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
from app.repository.danmaku_repo import (
    list_danmaku_by_stream_part,
)
from app.repository.stream_part_repo import (
    list_stream_parts,
)
from app.repository.stream_repo import (
    list_streams,
)
from scripts.import_archive import (
    import_stream,
)


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
)


TEST_VTUBER = Vtuber(
    id="vtuber-test",
    display_name="测试主播",
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
    vtuber_id: str = "vtuber-test",
    title: str = "测试直播",
) -> Stream:
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
        bv_ids=[],
        title=title,
        video_url="",
        status="local",
    )


def test_import_stream_persists_local_archive(
    tmp_path: Path,
) -> None:
    connection = make_connection()

    try:
        stream = make_stream()

        shutil.copy(
            FIXTURES / "sample.ass",
            tmp_path
            / f"{stream.title}.ass",
        )

        (
            tmp_path
            / f"{stream.title}.xml"
        ).touch()

        result = import_stream(
            connection=connection,
            stream=stream,
            vtuber=TEST_VTUBER,
            archive_root=tmp_path,
            layout="flat",
        )

        assert (
            result["status"]
            == "imported"
        )

        assert (
            result["layout"]
            == "flat"
        )

        assert (
            result["parts"]
            == 1
        )

        assert (
            result["danmaku"]
            == 2
        )

        streams = list_streams(
            connection=connection,
        )

        assert len(
            streams
        ) == 1

        assert (
            streams[0][
                "vtuber_id"
            ]
            == TEST_VTUBER.id
        )

        parts = list_stream_parts(
            connection=connection,
            stream_id=stream.id,
        )

        assert len(
            parts
        ) == 1

        danmaku = (
            list_danmaku_by_stream_part(
                connection=connection,
                stream_part_id=(
                    parts[0]["id"]
                ),
                stream_id=stream.id,
                part_id="p0",
            )
        )

        assert len(
            danmaku
        ) == 2

    finally:
        connection.close()


def test_import_stream_persists_metadata_only_stream(
    tmp_path: Path,
) -> None:
    connection = make_connection()

    try:
        stream = make_stream()

        result = import_stream(
            connection=connection,
            stream=stream,
            vtuber=TEST_VTUBER,
            archive_root=tmp_path,
            layout="flat",
        )

        assert (
            result["status"]
            == "metadata_only"
        )

        assert (
            result["parts"]
            == 0
        )

        assert (
            result["danmaku"]
            == 0
        )

        streams = list_streams(
            connection=connection,
        )

        assert len(
            streams
        ) == 1

        assert (
            streams[0]["id"]
            == stream.id
        )

        parts = list_stream_parts(
            connection=connection,
            stream_id=stream.id,
        )

        assert (
            parts
            == []
        )

    finally:
        connection.close()


def test_failed_stream_does_not_break_following_import(
    tmp_path: Path,
) -> None:
    connection = make_connection()

    try:
        invalid_stream = (
            make_stream(
                vtuber_id=(
                    "another-vtuber"
                ),
                title="错误直播",
            )
        )

        failed = import_stream(
            connection=connection,
            stream=invalid_stream,
            vtuber=TEST_VTUBER,
            archive_root=tmp_path,
            layout="flat",
        )

        assert (
            failed["status"]
            == "failed"
        )

        assert (
            connection.in_transaction
            is False
        )

        valid_stream = make_stream(
            title="正常直播",
        )

        shutil.copy(
            FIXTURES / "sample.ass",
            tmp_path
            / f"{valid_stream.title}.ass",
        )

        succeeded = import_stream(
            connection=connection,
            stream=valid_stream,
            vtuber=TEST_VTUBER,
            archive_root=tmp_path,
            layout="flat",
        )

        assert (
            succeeded["status"]
            == "imported"
        )

        streams = list_streams(
            connection=connection,
        )

        assert len(
            streams
        ) == 1

        assert (
            streams[0]["id"]
            == valid_stream.id
        )

    finally:
        connection.close()