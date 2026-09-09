from pathlib import Path

from app.ingestion.csv_loader import load_streams


path = Path(
    r"E:\repository\MikotoRecord\录播完整检查.csv"
)

streams = load_streams(path)

print("直播数量:", len(streams))

for stream in streams[:3]:
    print()
    print("ID:", stream.id)
    print("直播时间:", stream.live_time)
    print("发布时间:", stream.publish_times)
    print("标题:", stream.title)
    print("BV:", stream.bv_id)
    print("状态:", stream.status)