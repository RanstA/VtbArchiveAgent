import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ingestion.archive_scanner import scan_stream_directory


DEFAULT_DIRECTORY = Path(
    r"E:\repository\MikotoRecord\2025年9月录播\【直播回放】いろいろ聊 2025年09月11日19点场"
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect StreamPart groups in an archive directory.")
    parser.add_argument("directory", nargs="?", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--stream-id", default="test-stream")
    args = parser.parse_args()

    parts = scan_stream_directory(
        directory=args.directory,
        stream_id=args.stream_id,
    )

    print("识别到分片数量:", len(parts))
    for part in parts:
        print()
        print("part_id:", part.part_id)
        print("video:", part.video_path)
        print("ass:", part.danmaku_path)
        print("xml:", part.xml_path)


if __name__ == "__main__":
    main()
