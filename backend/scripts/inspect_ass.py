import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ingestion.ass_parser import parse_ass


DEFAULT_PATH = Path(
    r"E:\repository\MikotoRecord\2025年9月录播\【直播回放】いろいろ聊 2025年09月11日19点场\【直播回放】いろいろ聊 2025年09月11日19点场_32316327100.ass"
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect parsed danmaku from an ASS file.")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--stream-id", default="test-stream")
    parser.add_argument("--part-id", default="inspection-part")
    args = parser.parse_args()

    danmaku = parse_ass(
        path=args.path,
        stream_id=args.stream_id,
        part_id=args.part_id,
    )

    print("弹幕数量:", len(danmaku))
    for item in danmaku[:10]:
        print(item.part_id, item.timestamp_ms, item.text)

    assert all(item.timestamp_ms >= 0 for item in danmaku)
    assert all(item.text.strip() for item in danmaku)
    assert all(r"{\c" not in item.text for item in danmaku)
    assert all(r"\move" not in item.text for item in danmaku)


if __name__ == "__main__":
    main()
