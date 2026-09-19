from datetime import (
    datetime,
    timedelta,
    timezone,
)

from app.ingestion.bilibili_session import (
    BilibiliSessionStore,
)


def test_session_can_be_saved_and_loaded(
    tmp_path,
):
    path = (
        tmp_path
        / "bilibili_session.json"
    )

    store = BilibiliSessionStore(
        path
    )

    now = datetime(
        2026,
        9,
        19,
        8,
        0,
        tzinfo=timezone.utc,
    )

    saved = store.save(
        "test-sessdata",
        now=now,
    )

    loaded = store.load(
        now=(
            now
            + timedelta(
                hours=1
            )
        )
    )

    assert loaded is not None

    assert (
        loaded.sessdata
        == "test-sessdata"
    )

    assert (
        saved.expires_at
        == now
        + timedelta(
            hours=48
        )
    )


def test_expired_session_is_removed(
    tmp_path,
):
    path = (
        tmp_path
        / "bilibili_session.json"
    )

    store = BilibiliSessionStore(
        path
    )

    now = datetime(
        2026,
        9,
        19,
        8,
        0,
        tzinfo=timezone.utc,
    )

    store.save(
        "test-sessdata",
        now=now,
    )

    loaded = store.load(
        now=(
            now
            + timedelta(
                hours=49
            )
        )
    )

    assert loaded is None

    assert not path.exists()


def test_session_can_be_cleared(
    tmp_path,
):
    path = (
        tmp_path
        / "bilibili_session.json"
    )

    store = BilibiliSessionStore(
        path
    )

    store.save(
        "test-sessdata"
    )

    assert path.exists()

    store.clear()

    assert not path.exists()