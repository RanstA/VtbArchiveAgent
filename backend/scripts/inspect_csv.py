import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ingestion.csv_loader import load_streams


DEFAULT_PATH = Path(
    r"E:\repository\MikotoRecord\录播完整检查.csv"
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Stream models loaded from a CSV file.")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()

    streams = load_streams(args.path)

    print("直播数量:", len(streams))
    for stream in streams[:3]:
        print()
        print("ID:", stream.id)
        print("直播时间:", stream.live_time)
        print("发布时间:", stream.publish_times)
        print("标题:", stream.title)
        print("BV:", stream.bv_id)
        print("状态:", stream.status)


if __name__ == "__main__":
    main()
