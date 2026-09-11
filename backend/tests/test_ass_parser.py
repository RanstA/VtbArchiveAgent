from pathlib import Path

from app.ingestion.ass_parser import parse_ass


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_ass_removes_override_tags_and_builds_danmaku() -> None:
    danmaku = parse_ass(
        FIXTURES / "sample.ass",
        stream_id="stream-test",
        part_id="123",
    )

    assert len(danmaku) == 2
    assert all(item.stream_id == "stream-test" for item in danmaku)
    assert all(item.part_id == "123" for item in danmaku)
    assert all(item.timestamp_ms >= 0 for item in danmaku)
    assert all(item.text.strip() for item in danmaku)
    assert any(r"\move" in item.raw_text for item in danmaku)
    assert all(r"\move" not in item.text for item in danmaku)
    assert all(r"{\c" not in item.text for item in danmaku)


def test_parse_empty_ass_returns_empty_list() -> None:
    assert parse_ass(
        FIXTURES / "empty.ass",
        stream_id="stream-test",
        part_id="empty",
    ) == []
