import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ingestion.archive_scanner import scan_stream_directory
from app.ingestion.ass_parser import parse_ass


DEFAULT_DIRECTORY = Path(
    r"E:\repository\MikotoRecord\2025年9月录播\【直播回放】いろいろ聊 2025年09月11日19点场"
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect StreamPart and Danmaku relationships.")
    parser.add_argument("directory", nargs="?", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--stream-id", default="test-stream")
    args = parser.parse_args()

    parts = scan_stream_directory(
        directory=args.directory,
        stream_id=args.stream_id,
    )

    for part in parts:
        print()
        print("part_id:", part.part_id)

        if part.danmaku_path is None:
            print("没有 ASS")
            continue

        danmaku = parse_ass(
            path=Path(part.danmaku_path),
            stream_id=args.stream_id,
            part_id=part.part_id,
        )

        print("弹幕数量:", len(danmaku))
        for item in danmaku[:3]:
            print(item.part_id, item.timestamp_ms, item.text)


if __name__ == "__main__":
    main()
