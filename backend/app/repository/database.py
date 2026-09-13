import sqlite3
from pathlib import Path


def connect_db(
    db_path: Path,
) -> sqlite3.Connection:
    connection = sqlite3.connect(
        db_path
    )

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

            PRIMARY KEY (
                stream_id,
                bv_id
            ),

            FOREIGN KEY (
                stream_id
            )
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

            FOREIGN KEY (
                stream_id
            )
                REFERENCES streams(id)
                ON DELETE CASCADE,

            UNIQUE (
                stream_id,
                part_id
            )
        );


        CREATE TABLE IF NOT EXISTS danmaku (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            stream_part_id INTEGER NOT NULL,

            timestamp_ms INTEGER NOT NULL,

            raw_text TEXT NOT NULL,
            text TEXT NOT NULL,

            FOREIGN KEY (
                stream_part_id
            )
                REFERENCES stream_parts(id)
                ON DELETE CASCADE
        );


        CREATE TABLE IF NOT EXISTS highlights (
            id TEXT PRIMARY KEY,

            stream_id TEXT NOT NULL,
            part_id TEXT NOT NULL,

            start_ms INTEGER NOT NULL,
            end_ms INTEGER NOT NULL,
            peak_ms INTEGER NOT NULL,

            score REAL NOT NULL,

            density_score REAL NOT NULL,
            repetition_score REAL NOT NULL,
            reaction_score REAL NOT NULL,

            danmaku_count INTEGER NOT NULL,
            unique_text_count INTEGER NOT NULL,

            repetition_ratio REAL NOT NULL,
            reaction_ratio REAL NOT NULL,

            laugh_count INTEGER NOT NULL,
            question_count INTEGER NOT NULL,
            exclamation_count INTEGER NOT NULL,

            detector_version TEXT NOT NULL,

            CHECK (
                start_ms >= 0
            ),

            CHECK (
                end_ms > start_ms
            ),

            CHECK (
                peak_ms >= start_ms
                AND peak_ms < end_ms
            ),

            CHECK (
                score >= 0.0
                AND score <= 1.0
            ),

            CHECK (
                density_score >= 0.0
                AND density_score <= 1.0
            ),

            CHECK (
                repetition_score >= 0.0
                AND repetition_score <= 1.0
            ),

            CHECK (
                reaction_score >= 0.0
                AND reaction_score <= 1.0
            ),

            CHECK (
                repetition_ratio >= 0.0
                AND repetition_ratio <= 1.0
            ),

            CHECK (
                reaction_ratio >= 0.0
                AND reaction_ratio <= 1.0
            ),

            CHECK (
                danmaku_count >= 0
            ),

            CHECK (
                unique_text_count >= 0
            ),

            CHECK (
                laugh_count >= 0
            ),

            CHECK (
                question_count >= 0
            ),

            CHECK (
                exclamation_count >= 0
            ),

            FOREIGN KEY (
                stream_id,
                part_id
            )
                REFERENCES stream_parts(
                    stream_id,
                    part_id
                )
                ON DELETE CASCADE
        );


        CREATE INDEX IF NOT EXISTS
            idx_danmaku_part_time
        ON danmaku(
            stream_part_id,
            timestamp_ms
        );


        CREATE INDEX IF NOT EXISTS
            idx_highlights_stream_part_time
        ON highlights(
            stream_id,
            part_id,
            start_ms
        );


        CREATE INDEX IF NOT EXISTS
            idx_highlights_score
        ON highlights(
            score DESC
        );
        """
    )

    connection.commit()