import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from app.domain.event import (
    Event,
    make_event_id,
)
from app.domain.source.stream import (
    Stream,
    make_stream_id,
)
from app.domain.source.vtuber import (
    Vtuber,
)
from app.repository.database import (
    connect_db,
    init_db,
)
from app.repository.event_repo import (
    get_event_by_id,
    upsert_event,
)
from app.repository.stream_repo import (
    insert_stream,
)
from app.repository.vtuber_repo import (
    insert_vtuber,
)
from app.repository.event_repo import (
    get_event_by_id,
    list_events_by_stream,
    upsert_event,
)


def prepare_database(
    db_path: Path,
) -> tuple[
    sqlite3.Connection,
    str,
]:
    connection = connect_db(db_path)

    init_db(connection)

    vtuber = Vtuber(
        id="aza",
        display_name="阿萨Aza",
    )

    insert_vtuber(
        connection=connection,
        vtuber=vtuber,
    )

    live_time = datetime(
        2026,
        9,
        29,
        20,
        0,
    )

    stream_id = make_stream_id(
        vtuber_id="aza",
        live_time=live_time,
    )

    stream = Stream(
        id=stream_id,
        vtuber_id="aza",
        live_time=live_time,
        title="Event 测试直播",
    )

    insert_stream(
        connection=connection,
        stream=stream,
    )

    return (
        connection,
        stream_id,
    )


def make_event(
    stream_id: str,
    *,
    title: str = "神秘园环节",
    summary: str = ("主播进入神秘园相关话题。"),
    semanticizer_version: str = "v1",
) -> Event:
    start_ms = 100_000
    end_ms = 160_000

    return Event(
        id=make_event_id(
            stream_id=stream_id,
            start_ms=start_ms,
            end_ms=end_ms,
        ),
        stream_id=stream_id,
        source_part_ids=[
            "p0",
            "p1",
        ],
        start_ms=start_ms,
        end_ms=end_ms,
        anchor_ms=130_000,
        source_highlight_ids=[
            "highlight-1",
            "highlight-2",
        ],
        title=title,
        summary=summary,
        keywords=[
            "神秘园",
            "聊天",
        ],
        entities=[
            "神秘园",
        ],
        semantic_text=(f"{title}\n" f"{summary}\n" "神秘园\n" "聊天"),
        salience_score=0.97,
        segmenter_version=("highlight-merge-v1"),
        semanticizer_version=(semanticizer_version),
    )


def test_event_round_trip(
    tmp_path: Path,
):
    db_path = tmp_path / "event.db"

    (
        connection,
        stream_id,
    ) = prepare_database(db_path)

    try:
        event = make_event(stream_id)

        upsert_event(
            connection=connection,
            event=event,
        )

        loaded = get_event_by_id(
            connection=connection,
            event_id=event.id,
        )

        assert loaded == event

    finally:
        connection.close()


def test_get_missing_event_returns_none(
    tmp_path: Path,
):
    db_path = tmp_path / "event.db"

    (
        connection,
        _,
    ) = prepare_database(db_path)

    try:
        loaded = get_event_by_id(
            connection=connection,
            event_id="missing",
        )

        assert loaded is None

    finally:
        connection.close()


def test_upsert_updates_existing_event(
    tmp_path: Path,
):
    db_path = tmp_path / "event.db"

    (
        connection,
        stream_id,
    ) = prepare_database(db_path)

    try:
        original = make_event(
            stream_id,
            title="旧标题",
            summary="旧摘要",
            semanticizer_version="v1",
        )

        upsert_event(
            connection=connection,
            event=original,
        )

        updated = original.model_copy(
            update={
                "title": "新标题",
                "summary": "新摘要",
                "keywords": [
                    "新关键词",
                ],
                "entities": [
                    "新实体",
                ],
                "semantic_text": ("新标题\n" "新摘要\n" "新关键词\n" "新实体"),
                "salience_score": 0.99,
                "semanticizer_version": "v2",
            }
        )

        upsert_event(
            connection=connection,
            event=updated,
        )

        loaded = get_event_by_id(
            connection=connection,
            event_id=original.id,
        )

        assert loaded == updated

        assert loaded.id == original.id

    finally:
        connection.close()


def test_event_requires_existing_stream(
    tmp_path: Path,
):
    db_path = tmp_path / "event.db"

    connection = connect_db(db_path)

    try:
        init_db(connection)

        event = make_event("missing-stream")

        with pytest.raises(sqlite3.IntegrityError):
            upsert_event(
                connection=connection,
                event=event,
            )

    finally:
        connection.close()


def test_deleting_stream_cascades_events(
    tmp_path: Path,
):
    db_path = tmp_path / "event.db"

    (
        connection,
        stream_id,
    ) = prepare_database(db_path)

    try:
        event = make_event(stream_id)

        upsert_event(
            connection=connection,
            event=event,
        )

        assert (
            get_event_by_id(
                connection=connection,
                event_id=event.id,
            )
            is not None
        )

        with connection:
            connection.execute(
                """
                DELETE FROM streams
                WHERE id = ?
                """,
                (stream_id,),
            )

        assert (
            get_event_by_id(
                connection=connection,
                event_id=event.id,
            )
            is None
        )

    finally:
        connection.close()


import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from app.domain.event import (
    Event,
    make_event_id,
)
from app.domain.source.stream import (
    Stream,
    make_stream_id,
)
from app.domain.source.vtuber import (
    Vtuber,
)
from app.repository.database import (
    connect_db,
    init_db,
)
from app.repository.event_repo import (
    get_event_by_id,
    upsert_event,
)
from app.repository.stream_repo import (
    insert_stream,
)
from app.repository.vtuber_repo import (
    insert_vtuber,
)


def prepare_database(
    db_path: Path,
) -> tuple[
    sqlite3.Connection,
    str,
]:
    connection = connect_db(db_path)

    init_db(connection)

    vtuber = Vtuber(
        id="aza",
        display_name="阿萨Aza",
    )

    insert_vtuber(
        connection=connection,
        vtuber=vtuber,
    )

    live_time = datetime(
        2026,
        9,
        29,
        20,
        0,
    )

    stream_id = make_stream_id(
        vtuber_id="aza",
        live_time=live_time,
    )

    stream = Stream(
        id=stream_id,
        vtuber_id="aza",
        live_time=live_time,
        title="Event 测试直播",
    )

    insert_stream(
        connection=connection,
        stream=stream,
    )

    return (
        connection,
        stream_id,
    )


def make_event(
    stream_id: str,
    *,
    title: str = "神秘园环节",
    summary: str = ("主播进入神秘园相关话题。"),
    semanticizer_version: str = "v1",
) -> Event:
    start_ms = 100_000
    end_ms = 160_000

    return Event(
        id=make_event_id(
            stream_id=stream_id,
            start_ms=start_ms,
            end_ms=end_ms,
        ),
        stream_id=stream_id,
        source_part_ids=[
            "p0",
            "p1",
        ],
        start_ms=start_ms,
        end_ms=end_ms,
        anchor_ms=130_000,
        source_highlight_ids=[
            "highlight-1",
            "highlight-2",
        ],
        title=title,
        summary=summary,
        keywords=[
            "神秘园",
            "聊天",
        ],
        entities=[
            "神秘园",
        ],
        semantic_text=(f"{title}\n" f"{summary}\n" "神秘园\n" "聊天"),
        salience_score=0.97,
        segmenter_version=("highlight-merge-v1"),
        semanticizer_version=(semanticizer_version),
    )


def test_event_round_trip(
    tmp_path: Path,
):
    db_path = tmp_path / "event.db"

    (
        connection,
        stream_id,
    ) = prepare_database(db_path)

    try:
        event = make_event(stream_id)

        upsert_event(
            connection=connection,
            event=event,
        )

        loaded = get_event_by_id(
            connection=connection,
            event_id=event.id,
        )

        assert loaded == event

    finally:
        connection.close()


def test_get_missing_event_returns_none(
    tmp_path: Path,
):
    db_path = tmp_path / "event.db"

    (
        connection,
        _,
    ) = prepare_database(db_path)

    try:
        loaded = get_event_by_id(
            connection=connection,
            event_id="missing",
        )

        assert loaded is None

    finally:
        connection.close()


def test_upsert_updates_existing_event(
    tmp_path: Path,
):
    db_path = tmp_path / "event.db"

    (
        connection,
        stream_id,
    ) = prepare_database(db_path)

    try:
        original = make_event(
            stream_id,
            title="旧标题",
            summary="旧摘要",
            semanticizer_version="v1",
        )

        upsert_event(
            connection=connection,
            event=original,
        )

        updated = original.model_copy(
            update={
                "title": "新标题",
                "summary": "新摘要",
                "keywords": [
                    "新关键词",
                ],
                "entities": [
                    "新实体",
                ],
                "semantic_text": ("新标题\n" "新摘要\n" "新关键词\n" "新实体"),
                "salience_score": 0.99,
                "semanticizer_version": "v2",
            }
        )

        upsert_event(
            connection=connection,
            event=updated,
        )

        loaded = get_event_by_id(
            connection=connection,
            event_id=original.id,
        )

        assert loaded == updated

        assert loaded.id == original.id

    finally:
        connection.close()


def test_event_requires_existing_stream(
    tmp_path: Path,
):
    db_path = tmp_path / "event.db"

    connection = connect_db(db_path)

    try:
        init_db(connection)

        event = make_event("missing-stream")

        with pytest.raises(sqlite3.IntegrityError):
            upsert_event(
                connection=connection,
                event=event,
            )

    finally:
        connection.close()


def test_deleting_stream_cascades_events(
    tmp_path: Path,
):
    db_path = tmp_path / "event.db"

    (
        connection,
        stream_id,
    ) = prepare_database(db_path)

    try:
        event = make_event(stream_id)

        upsert_event(
            connection=connection,
            event=event,
        )

        assert (
            get_event_by_id(
                connection=connection,
                event_id=event.id,
            )
            is not None
        )

        with connection:
            connection.execute(
                """
                DELETE FROM streams
                WHERE id = ?
                """,
                (stream_id,),
            )

        assert (
            get_event_by_id(
                connection=connection,
                event_id=event.id,
            )
            is None
        )

    finally:
        connection.close()


def test_list_events_by_stream_orders_by_time(
    tmp_path: Path,
):
    db_path = tmp_path / "event.db"

    (
        connection,
        stream_id,
    ) = prepare_database(db_path)

    try:
        later = make_event(stream_id).model_copy(
            update={
                "id": make_event_id(
                    stream_id=stream_id,
                    start_ms=300_000,
                    end_ms=360_000,
                ),
                "start_ms": 300_000,
                "end_ms": 360_000,
                "anchor_ms": 330_000,
                "title": "后一个事件",
            }
        )

        earlier = make_event(stream_id).model_copy(
            update={
                "id": make_event_id(
                    stream_id=stream_id,
                    start_ms=20_000,
                    end_ms=80_000,
                ),
                "start_ms": 20_000,
                "end_ms": 80_000,
                "anchor_ms": 50_000,
                "title": "前一个事件",
            }
        )

        upsert_event(
            connection=connection,
            event=later,
        )

        upsert_event(
            connection=connection,
            event=earlier,
        )

        events = list_events_by_stream(
            connection=connection,
            stream_id=stream_id,
        )

        assert [event.id for event in events] == [
            earlier.id,
            later.id,
        ]

    finally:
        connection.close()
