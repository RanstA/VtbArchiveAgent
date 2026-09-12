from pathlib import Path
from app.repository.database import connect_db

connection = connect_db(Path("vtuber_archive.db"))
print("=== Stream 数量 ===")

row = connection.execute(
    "SELECT COUNT(*) FROM streams"
).fetchone()

print(row[0])

print("\n=== StreamPart 数量 ===")
row = connection.execute(
    "SELECT COUNT(*) FROM stream_parts"
).fetchone()

print(row[0])


print("\n=== Danmaku 数量 ===")
row = connection.execute(
    "SELECT COUNT(*) FROM danmaku"
).fetchone()

print(row[0])
print("\n=== 每个 Part 的弹幕数量 ===")

rows = connection.execute(
    """
    SELECT
        stream_parts.part_id,
        COUNT(danmaku.id)
    FROM stream_parts
    LEFT JOIN danmaku
        ON danmaku.stream_part_id = stream_parts.id
    GROUP BY stream_parts.id
    """
).fetchall()

for row in rows:
    print(row)
    
print("\n=== BV 数量 ===")

row = connection.execute(
    """
    SELECT COUNT(*)
    FROM stream_bv_ids
    """
).fetchone()

print(row[0])

print("\n=== Stream 与 BV ===")

rows = connection.execute(
    """
    SELECT
        streams.title,
        stream_bv_ids.bv_id
    FROM streams
    LEFT JOIN stream_bv_ids
        ON stream_bv_ids.stream_id = streams.id
    ORDER BY stream_bv_ids.bv_id
    """
).fetchall()

for row in rows:
    print(row)

connection.close()