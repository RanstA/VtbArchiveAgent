from pathlib import Path

from app.ingestion.archive_scanner import scan_stream_directory


def create_empty_file(path: Path) -> None:
    path.touch()


def test_scanner_groups_same_stem_and_extracts_trailing_part_id(tmp_path: Path) -> None:
    for suffix in (".mp4", ".ass", ".xml"):
        create_empty_file(tmp_path / f"archive_clip123{suffix}")

    parts = scan_stream_directory(tmp_path, stream_id="stream-test")

    assert len(parts) == 1
    part = parts[0]
    assert part.stream_id == "stream-test"
    assert part.part_id == "123"
    assert part.video_path == str(tmp_path / "archive_clip123.mp4")
    assert part.danmaku_path == str(tmp_path / "archive_clip123.ass")
    assert part.xml_path == str(tmp_path / "archive_clip123.xml")


def test_scanner_finds_multiple_parts_and_marks_missing_paths(tmp_path: Path) -> None:
    for suffix in (".mp4", ".ass", ".xml"):
        create_empty_file(tmp_path / f"archive_123{suffix}")
    create_empty_file(tmp_path / "archive_456.mp4")
    create_empty_file(tmp_path / "archive_456.xml")
    create_empty_file(tmp_path / "ignored.txt")

    parts = scan_stream_directory(tmp_path, stream_id="stream-test")
    by_part_id = {part.part_id: part for part in parts}

    assert set(by_part_id) == {"123", "456"}
    assert by_part_id["123"].danmaku_path == str(tmp_path / "archive_123.ass")
    assert by_part_id["456"].video_path == str(tmp_path / "archive_456.mp4")
    assert by_part_id["456"].danmaku_path is None
    assert by_part_id["456"].xml_path == str(tmp_path / "archive_456.xml")
