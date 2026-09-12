from pathlib import Path
from app.ingestion.csv_loader import load_streams
from app.ingestion.archive_scanner import scan_stream_directory
from app.ingestion.ass_parser import parse_ass

from app.repository.database import connect_db, init_db
from app.repository.stream_repo import insert_stream
from app.repository.stream_part_repo import insert_stream_part
from app.repository.danmaku_repo import insert_danmaku_batch


CSV_PATH = Path(
    r"E:\repository\MikotoRecord\录播完整检查.csv"
)
STREAM_DIR = Path(
    r"E:\repository\MikotoRecord\2025年9月录播\【直播回放】いろいろ聊 2025年09月11日19点场"
)

DB_PATH = Path("vtuber_archive.db")

streams = load_streams(CSV_PATH)

stream = next(
    s for s in streams
    if "2025年09月11日19点场" in s.title
)

print("准备导入:")
print(stream.title)
print("stream_id:", stream.id)
print("BV:", stream.bv_ids)

connection = connect_db(DB_PATH)
init_db(connection)

try:
    insert_stream(connection, stream)
    parts = scan_stream_directory(
        directory=STREAM_DIR,
        stream_id=stream.id,
    )
    for part in parts:
        stream_part_id = insert_stream_part(
            connection,
            part,
        )
        print()
        print("Part:", part.part_id)
        if part.danmaku_path is None:
            print("没有 ASS，跳过")
            continue

        danmaku = parse_ass(
            path=Path(part.danmaku_path),
            stream_id=stream.id,
            part_id=part.part_id,
        )

        insert_danmaku_batch(
            connection,
            stream_part_id,
            danmaku,
        )

        print("写入弹幕:", len(danmaku))
    connection.commit()

    print()
    print("导入成功")
except Exception:
    connection.rollback()
    raise
finally:
    connection.close()