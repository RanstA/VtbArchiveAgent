from datetime import datetime
from pathlib import Path

from app.domain.stream import (
    Stream,
    make_stream_id,
)
from app.ingestion.csv_loader import (
    load_streams,
)


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
)


def test_load_streams_parses_stream_and_multiple_publish_times() -> None:
    streams = load_streams(
        FIXTURES / "sample.csv",
        vtuber_id="vtuber-test",
    )

    assert len(streams) == 2

    assert all(
        isinstance(
            stream,
            Stream,
        )
        for stream in streams
    )

    stream = streams[0]

    assert (
        stream.vtuber_id
        == "vtuber-test"
    )

    assert (
        stream.id
        == make_stream_id(
            vtuber_id="vtuber-test",
            live_time=datetime(
                2025,
                9,
                11,
                19,
                0,
            ),
            title="测试直播",
        )
    )

    assert (
        stream.bv_ids
        == ["BV1TEST123"]
    )

    assert (
        stream.title
        == "测试直播"
    )

    assert (
        stream.live_time
        == datetime(
            2025,
            9,
            11,
            19,
            0,
        )
    )

    assert (
        stream.publish_times
        == [
            datetime(
                2025,
                9,
                12,
                10,
                0,
            ),
            datetime(
                2025,
                9,
                13,
                11,
                30,
            ),
        ]
    )


def test_load_streams_allows_empty_publish_times() -> None:
    streams = load_streams(
        FIXTURES / "sample.csv",
        vtuber_id="vtuber-test",
    )

    assert (
        streams[1]
        .publish_times
        == []
    )


def test_same_stream_metadata_for_different_vtubers_has_different_id() -> None:
    first = load_streams(
        FIXTURES / "sample.csv",
        vtuber_id="vtuber-a",
    )[0]

    second = load_streams(
        FIXTURES / "sample.csv",
        vtuber_id="vtuber-b",
    )[0]

    assert (
        first.title
        == second.title
    )

    assert (
        first.live_time
        == second.live_time
    )

    assert (
        first.id
        != second.id
    )


def test_load_streams_rejects_empty_vtuber_id() -> None:
    try:
        load_streams(
            FIXTURES / "sample.csv",
            vtuber_id="",
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "empty vtuber_id "
            "should be rejected"
        )