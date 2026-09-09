from pathlib import Path

from app.ingestion.archive_scanner import scan_stream_directory


directory = Path(
    r"E:\repository\MikotoRecord\2025年9月录播\【直播回放】いろいろ聊 2025年09月11日19点场"
)

parts = scan_stream_directory(
    directory=directory,
    stream_id="test-stream",
)

print("识别到分片数量:", len(parts))

for part in parts:
    print()
    print("part_id:", part.part_id)
    print("video:", part.video_path)
    print("ass:", part.danmaku_path)
    print("xml:", part.xml_path)