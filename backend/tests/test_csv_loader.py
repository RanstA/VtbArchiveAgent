from datetime import datetime
from pathlib import Path

import pytest

from app.domain.source.stream import Stream, StreamStatus, make_stream_id
from app.ingestion.csv_loader import load_streams

FIXTURES = Path(__file__).parent / "fixtures"


def test_csv_loads_v1_streams_without_mapping_publication_status() -> None:
    streams = load_streams(FIXTURES / "sample.csv", vtuber_id="vtuber-test")
    assert len(streams) == 2
    assert all(isinstance(stream, Stream) for stream in streams)

    stream = streams[0]
    assert stream.vtuber_id == "vtuber-test"
    assert stream.id == make_stream_id(
        vtuber_id="vtuber-test",
        live_time=datetime(2025, 9, 11, 19, 0),
    )
    assert stream.title == "测试直播"
    assert stream.live_time == datetime(2025, 9, 11, 19, 0)
    assert all(item.status == StreamStatus.PENDING for item in streams)
    assert set(stream.model_dump()) == {
        "id", "vtuber_id", "live_time", "title", "status"
    }


def test_same_live_time_for_different_vtubers_has_different_id() -> None:
    first = load_streams(FIXTURES / "sample.csv", vtuber_id="vtuber-a")[0]
    second = load_streams(FIXTURES / "sample.csv", vtuber_id="vtuber-b")[0]
    assert first.title == second.title
    assert first.live_time == second.live_time
    assert first.id != second.id


def test_load_streams_rejects_empty_vtuber_id() -> None:
    with pytest.raises(ValueError, match="vtuber_id"):
        load_streams(FIXTURES / "sample.csv", vtuber_id="")
