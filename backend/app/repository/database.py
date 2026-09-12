import sqlite3
from pathlib import Path


def connect_db(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def init_db(
    connection: sqlite3.Connection,
) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS streams (
            id TEXT PRIMARY KEY,

            month TEXT NOT NULL,
            live_time TEXT NOT NULL,
            publish_times TEXT NOT NULL,

            title TEXT NOT NULL,
            video_url TEXT NOT NULL,
            status TEXT NOT NULL
        );


        CREATE TABLE IF NOT EXISTS stream_bv_ids (
            stream_id TEXT NOT NULL,
            bv_id TEXT NOT NULL,

            PRIMARY KEY (stream_id, bv_id),

            FOREIGN KEY (stream_id)
                REFERENCES streams(id)
                ON DELETE CASCADE
        );


        CREATE TABLE IF NOT EXISTS stream_parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            stream_id TEXT NOT NULL,
            part_id TEXT NOT NULL,

            video_path TEXT,
            danmaku_path TEXT,
            xml_path TEXT,

            FOREIGN KEY (stream_id)
                REFERENCES streams(id)
                ON DELETE CASCADE,

            UNIQUE (stream_id, part_id)
        );


        CREATE TABLE IF NOT EXISTS danmaku (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            stream_part_id INTEGER NOT NULL,
            timestamp_ms INTEGER NOT NULL,

            raw_text TEXT NOT NULL,
            text TEXT NOT NULL,

            FOREIGN KEY (stream_part_id)
                REFERENCES stream_parts(id)
                ON DELETE CASCADE
        );
        """
    )

    connection.commit()