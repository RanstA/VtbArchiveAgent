from datetime import datetime
from pathlib import Path

from app.domain.stream import Stream
from app.ingestion.csv_loader import load_streams


FIXTURES = Path(__file__).parent / "fixtures"


def test_load_streams_parses_stream_and_multiple_publish_times() -> None:
    streams = load_streams(FIXTURES / "sample.csv")

    assert len(streams) == 2
    assert all(isinstance(stream, Stream) for stream in streams)

    stream = streams[0]
    assert stream.id == "BV1TEST123"
    assert stream.bv_id == "BV1TEST123"
    assert stream.title == "测试直播"
    assert stream.live_time == datetime(2025, 9, 11, 19, 0)
    assert stream.publish_times == [
        datetime(2025, 9, 12, 10, 0),
        datetime(2025, 9, 13, 11, 30),
    ]


def test_load_streams_allows_empty_publish_times() -> None:
    streams = load_streams(FIXTURES / "sample.csv")

    assert streams[1].publish_times == []
