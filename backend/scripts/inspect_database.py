from pathlib import Path

from app.repository.database import connect_db, init_db


db_path = Path("vtuber_archive.db")

connection = connect_db(db_path)

init_db(connection)

print("数据库初始化完成")

cursor = connection.execute(
    """
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
    ORDER BY name;
    """
)

print("当前数据表:")

for row in cursor.fetchall():
    print("-", row[0])

connection.close()