import sqlite3

from pathlib import Path


def connect_db(
    db_path: Path,
) -> sqlite3.Connection:

    connection = sqlite3.connect(db_path)

    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def _table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:

    row = connection.execute(
        """

        SELECT 1

        FROM sqlite_master

        WHERE

            type = 'table'

            AND name = ?

        LIMIT 1

        """,
        (table_name,),
    ).fetchone()

    return row is not None


def _table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:

    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()

    return {row[1] for row in rows}


def _assert_schema_compatible(
    connection: sqlite3.Connection,
) -> None:
    """

    当前项目仍处于开发阶段，

    暂时不对旧数据库做自动迁移。



    如果检测到旧 schema，

    明确拒绝继续初始化，

    避免产生语义错误的数据。

    """

    if _table_exists(connection, "vtuber_sources") or _table_exists(
        connection, "stream_bv_ids"
    ):

        raise RuntimeError(
            "Legacy Source tables detected; re-import into a new database"
        )

    if not _table_exists(
        connection,
        "streams",
    ):

        return

    stream_columns = _table_columns(
        connection,
        "streams",
    )

    required = {"id", "vtuber_id", "live_time", "title", "status"}

    if stream_columns != required:

        raise RuntimeError(
            "Legacy database schema detected: "
            "streams must use Source V1 fields. "
            "Back up or remove the old development "
            "database and re-import the archive."
        )

    if not _table_exists(
        connection,
        "stream_parts",
    ):

        return

    part_columns = _table_columns(
        connection,
        "stream_parts",
    )

    required_part_columns = {
        "start_offset_ms",
        "duration_ms",
        "bvid",
        "cid",
        "page",
    }

    missing_part_columns = required_part_columns - part_columns

    if missing_part_columns:

        missing_text = ", ".join(sorted(missing_part_columns))

        raise RuntimeError(
            "Legacy database schema detected: "
            "stream_parts is missing "
            f"{missing_text}. "
            "Back up or remove the old development "
            "database and re-import the archive."
        )


def init_db(
    connection: sqlite3.Connection,
) -> None:

    _assert_schema_compatible(connection)

    connection.executescript("""

        CREATE TABLE IF NOT EXISTS vtubers (

            id TEXT PRIMARY KEY,

            display_name TEXT NOT NULL

        );





        CREATE TABLE IF NOT EXISTS streams (

            id TEXT PRIMARY KEY,



            vtuber_id TEXT NOT NULL,



            live_time TEXT NOT NULL,

            title TEXT NOT NULL,

            status TEXT NOT NULL,



            FOREIGN KEY (

                vtuber_id

            )

                REFERENCES vtubers(id)

                ON DELETE RESTRICT

        );





        CREATE TABLE IF NOT EXISTS stream_parts (

            id INTEGER PRIMARY KEY AUTOINCREMENT,



            stream_id TEXT NOT NULL,

            part_id TEXT NOT NULL,



            start_offset_ms INTEGER NOT NULL,

            bvid TEXT,

            cid TEXT,

            page INTEGER,

            duration_ms INTEGER,



            video_path TEXT,

            danmaku_path TEXT,

            xml_path TEXT,



            CHECK (

                start_offset_ms >= 0

            ),



            CHECK (

                duration_ms IS NULL

                OR duration_ms > 0

            ),



            CHECK (page IS NULL OR page >= 1),



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





        CREATE TABLE IF NOT EXISTS transcript_segments (

            id TEXT PRIMARY KEY,



            stream_id TEXT NOT NULL,

            part_id TEXT NOT NULL,



            start_ms INTEGER NOT NULL,

            end_ms INTEGER NOT NULL,



            raw_text TEXT NOT NULL,

            text TEXT NOT NULL,



            source TEXT NOT NULL,



            CHECK (start_ms >= 0),

            CHECK (end_ms > start_ms),



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



        CREATE TABLE IF NOT EXISTS reaction_matches (

            id TEXT PRIMARY KEY,



            stream_id TEXT NOT NULL,

            part_id TEXT NOT NULL,



            highlight_id TEXT NOT NULL UNIQUE,



            matcher_version TEXT NOT NULL,



            FOREIGN KEY (

                stream_id,

                part_id

            )

                REFERENCES stream_parts(

                    stream_id,

                    part_id

                )

                ON DELETE CASCADE,



            FOREIGN KEY (

                highlight_id

            )

                REFERENCES highlights(id)

                ON DELETE CASCADE

        );





        CREATE TABLE IF NOT EXISTS reaction_match_transcripts (

            reaction_match_id TEXT NOT NULL,

            transcript_segment_id TEXT NOT NULL,

            position INTEGER NOT NULL,



            PRIMARY KEY (

                reaction_match_id,

                transcript_segment_id

            ),



            UNIQUE (

                reaction_match_id,

                position

            ),



            CHECK (

                position >= 0

            ),



            FOREIGN KEY (

                reaction_match_id

            )

                REFERENCES reaction_matches(id)

                ON DELETE CASCADE,



            FOREIGN KEY (

                transcript_segment_id

            )

                REFERENCES transcript_segments(id)

                ON DELETE CASCADE

        );



        CREATE TABLE IF NOT EXISTS reaction_match_danmaku (

            reaction_match_id TEXT NOT NULL,

            danmaku_id INTEGER NOT NULL,

            position INTEGER NOT NULL,



            PRIMARY KEY (

                reaction_match_id,

                danmaku_id

            ),



            UNIQUE (

                reaction_match_id,

                position

            ),



            CHECK (

                position >= 0

            ),



            FOREIGN KEY (

                reaction_match_id

            )

                REFERENCES reaction_matches(id)

                ON DELETE CASCADE,



            FOREIGN KEY (

                danmaku_id

            )

                REFERENCES danmaku(id)

                ON DELETE CASCADE

        );



        CREATE INDEX IF NOT EXISTS

            idx_reaction_matches_stream_part

        ON reaction_matches(

            stream_id,

            part_id

        );







        CREATE TABLE IF NOT EXISTS topic_segments (
            id TEXT PRIMARY KEY,

            stream_id TEXT NOT NULL,

            start_ms INTEGER NOT NULL,
            end_ms INTEGER NOT NULL,

            title TEXT NOT NULL,
            summary TEXT NOT NULL,

            salience_score REAL NOT NULL,
            confidence REAL NOT NULL,

            analyzer_version TEXT NOT NULL,

            CHECK (
                start_ms >= 0
            ),

            CHECK (
                end_ms > start_ms
            ),

            CHECK (
                salience_score >= 0.0
                AND salience_score <= 1.0
            ),

            CHECK (
                confidence >= 0.0
                AND confidence <= 1.0
            ),

            FOREIGN KEY (
                stream_id
            )
                REFERENCES streams(id)
                ON DELETE CASCADE
        );


        CREATE TABLE IF NOT EXISTS topic_segment_parts (
            topic_segment_id TEXT NOT NULL,
            part_id TEXT NOT NULL,
            position INTEGER NOT NULL,

            PRIMARY KEY (
                topic_segment_id,
                part_id
            ),

            UNIQUE (
                topic_segment_id,
                position
            ),

            CHECK (
                position >= 0
            ),

            FOREIGN KEY (
                topic_segment_id
            )
                REFERENCES topic_segments(id)
                ON DELETE CASCADE
        );


        CREATE TABLE IF NOT EXISTS topic_segment_reaction_matches (
            topic_segment_id TEXT NOT NULL,
            reaction_match_id TEXT NOT NULL,
            position INTEGER NOT NULL,

            PRIMARY KEY (
                topic_segment_id,
                reaction_match_id
            ),

            UNIQUE (
                topic_segment_id,
                position
            ),

            CHECK (
                position >= 0
            ),

            FOREIGN KEY (
                topic_segment_id
            )
                REFERENCES topic_segments(id)
                ON DELETE CASCADE,

            FOREIGN KEY (
                reaction_match_id
            )
                REFERENCES reaction_matches(id)
                ON DELETE CASCADE
        );


        CREATE TABLE IF NOT EXISTS topic_segment_transcripts (
            topic_segment_id TEXT NOT NULL,
            transcript_segment_id TEXT NOT NULL,
            position INTEGER NOT NULL,

            PRIMARY KEY (
                topic_segment_id,
                transcript_segment_id
            ),

            UNIQUE (
                topic_segment_id,
                position
            ),

            CHECK (
                position >= 0
            ),

            FOREIGN KEY (
                topic_segment_id
            )
                REFERENCES topic_segments(id)
                ON DELETE CASCADE,

            FOREIGN KEY (
                transcript_segment_id
            )
                REFERENCES transcript_segments(id)
                ON DELETE CASCADE
        );


        CREATE TABLE IF NOT EXISTS topic_segment_keywords (
            topic_segment_id TEXT NOT NULL,
            keyword TEXT NOT NULL,
            position INTEGER NOT NULL,

            PRIMARY KEY (
                topic_segment_id,
                keyword
            ),

            UNIQUE (
                topic_segment_id,
                position
            ),

            CHECK (
                position >= 0
            ),

            FOREIGN KEY (
                topic_segment_id
            )
                REFERENCES topic_segments(id)
                ON DELETE CASCADE
        );


        CREATE TABLE IF NOT EXISTS topic_segment_entities (
            topic_segment_id TEXT NOT NULL,
            entity TEXT NOT NULL,
            position INTEGER NOT NULL,

            PRIMARY KEY (
                topic_segment_id,
                entity
            ),

            UNIQUE (
                topic_segment_id,
                position
            ),

            CHECK (
                position >= 0
            ),

            FOREIGN KEY (
                topic_segment_id
            )
                REFERENCES topic_segments(id)
                ON DELETE CASCADE
        );


        CREATE INDEX IF NOT EXISTS
            idx_topic_segments_stream_time
        ON topic_segments(
            stream_id,
            start_ms
        );


        CREATE INDEX IF NOT EXISTS
            idx_topic_segments_salience
        ON topic_segments(
            salience_score DESC
        );


        CREATE TABLE IF NOT EXISTS events (

            id TEXT PRIMARY KEY,



            stream_id TEXT NOT NULL,



            source_part_ids TEXT NOT NULL,



            start_ms INTEGER NOT NULL,

            end_ms INTEGER NOT NULL,

            anchor_ms INTEGER NOT NULL,



            source_highlight_ids TEXT NOT NULL,



            title TEXT NOT NULL,

            summary TEXT NOT NULL,



            keywords TEXT NOT NULL,

            entities TEXT NOT NULL,



            semantic_text TEXT NOT NULL,



            salience_score REAL NOT NULL,



            segmenter_version TEXT NOT NULL,

            semanticizer_version TEXT NOT NULL,



            CHECK (

                start_ms >= 0

            ),



            CHECK (

                end_ms > start_ms

            ),



            CHECK (

                anchor_ms >= start_ms

                AND anchor_ms < end_ms

            ),



            CHECK (

                salience_score >= 0.0

                AND salience_score <= 1.0

            ),



            FOREIGN KEY (

                stream_id

            )

                REFERENCES streams(id)

                ON DELETE CASCADE

        );





        CREATE INDEX IF NOT EXISTS

            idx_streams_vtuber_live_time

        ON streams(

            vtuber_id,

            live_time DESC

        );





        CREATE INDEX IF NOT EXISTS

            idx_danmaku_part_time

        ON danmaku(

            stream_part_id,

            timestamp_ms

        );





        CREATE INDEX IF NOT EXISTS

            idx_transcript_segments_stream_part_time

        ON transcript_segments(

            stream_id,

            part_id,

            start_ms

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





        CREATE INDEX IF NOT EXISTS

            idx_events_stream_time

        ON events(

            stream_id,

            start_ms

        );





        CREATE INDEX IF NOT EXISTS

            idx_events_salience

        ON events(

            salience_score DESC

        );

        """)

    connection.commit()
