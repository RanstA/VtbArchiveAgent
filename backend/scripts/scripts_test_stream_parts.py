from pathlib import Path

from app.ingestion.archive_scanner import scan_stream_directory
from app.ingestion.ass_parser import parse_ass


directory = Path(
    r"E:\repository\MikotoRecord\2025年9月录播\【直播回放】いろいろ聊 2025年09月11日19点场"
)

stream_id = "test-stream"

parts = scan_stream_directory(
    directory=directory,
    stream_id=stream_id,
)

for part in parts:
    print()
    print("part_id:", part.part_id)

    if part.danmaku_path is None:
        print("没有 ASS")
        continue

    danmaku = parse_ass(
        path=Path(part.danmaku_path),
        stream_id=stream_id,
        part_id=part.part_id,
    )

    print("弹幕数量:", len(danmaku))

    for item in danmaku[:3]:
        print(
            item.part_id,
            item.timestamp_ms,
            item.text,
        )
