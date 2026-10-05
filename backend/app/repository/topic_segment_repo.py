import sqlite3

from app.domain.pipeline.topic_segment import (
    TopicSegment,
)
from app.repository.reaction_match_repo import (
    get_reaction_match_by_id,
)


def _validate_no_duplicates(
    values: list,
    *,
    field_name: str,
) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {field_name}")


def _validate_topic_segment(
    connection: sqlite3.Connection,
    topic_segment: TopicSegment,
) -> None:
    """
    验证 TopicSegment 的持久化关系。

    Repository 不负责重新进行语义分析，
    但必须保证所有关系都能追溯到真实的
    StreamPart / ReactionMatch / Transcript Evidence。
    """

    _validate_no_duplicates(
        topic_segment.source_part_ids,
        field_name="source_part_ids",
    )

    _validate_no_duplicates(
        topic_segment.reaction_match_ids,
        field_name="reaction_match_ids",
    )

    _validate_no_duplicates(
        topic_segment.transcript_segment_ids,
        field_name="transcript_segment_ids",
    )

    _validate_no_duplicates(
        topic_segment.keywords,
        field_name="keywords",
    )

    _validate_no_duplicates(
        topic_segment.entities,
        field_name="entities",
    )

    stream_row = connection.execute(
        """
        SELECT id
        FROM streams
        WHERE id = ?
        """,
        (topic_segment.stream_id,),
    ).fetchone()

    if stream_row is None:
        raise ValueError("stream does not exist: " f"{topic_segment.stream_id}")

    available_part_rows = connection.execute(
        """
        SELECT part_id
        FROM stream_parts
        WHERE stream_id = ?
        ORDER BY start_offset_ms ASC
        """,
        (topic_segment.stream_id,),
    ).fetchall()

    available_part_ids = {row[0] for row in available_part_rows}

    for part_id in topic_segment.source_part_ids:
        if part_id not in available_part_ids:
            raise ValueError(
                "StreamPart does not belong to " "topic segment stream: " f"{part_id}"
            )

    expected_part_ids: list[str] = []
    allowed_transcript_ids: set[str] = set()

    for reaction_match_id in topic_segment.reaction_match_ids:
        reaction_match = get_reaction_match_by_id(
            connection,
            reaction_match_id,
        )

        if reaction_match is None:
            raise ValueError("reaction match does not exist: " f"{reaction_match_id}")

        if reaction_match.stream_id != topic_segment.stream_id:
            raise ValueError(
                "reaction match does not belong "
                "to topic segment stream: "
                f"{reaction_match_id}"
            )

        if reaction_match.part_id not in expected_part_ids:
            expected_part_ids.append(reaction_match.part_id)

        allowed_transcript_ids.update(reaction_match.transcript_segment_ids)

    if topic_segment.source_part_ids != expected_part_ids:
        raise ValueError("source_part_ids do not match " "reaction match parts")

    for transcript_segment_id in topic_segment.transcript_segment_ids:
        if transcript_segment_id not in allowed_transcript_ids:
            raise ValueError(
                "transcript segment is not supported "
                "by topic reaction matches: "
                f"{transcript_segment_id}"
            )

        row = connection.execute(
            """
            SELECT
                stream_id,
                part_id
            FROM transcript_segments
            WHERE id = ?
            """,
            (transcript_segment_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                "transcript segment does not exist: " f"{transcript_segment_id}"
            )

        if row[0] != topic_segment.stream_id:
            raise ValueError(
                "transcript segment does not belong "
                "to topic segment stream: "
                f"{transcript_segment_id}"
            )

        if row[1] not in topic_segment.source_part_ids:
            raise ValueError(
                "transcript segment does not belong "
                "to topic segment source parts: "
                f"{transcript_segment_id}"
            )


def _insert_rows(
    connection: sqlite3.Connection,
    topic_segment: TopicSegment,
) -> None:
    connection.execute(
        """
        INSERT INTO topic_segments (
            id,
            stream_id,
            start_ms,
            end_ms,
            topic_type,
            title,
            summary,
            salience_score,
            confidence,
            analyzer_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            topic_segment.id,
            topic_segment.stream_id,
            topic_segment.start_ms,
            topic_segment.end_ms,
            topic_segment.topic_type,
            topic_segment.title,
            topic_segment.summary,
            topic_segment.salience_score,
            topic_segment.confidence,
            topic_segment.analyzer_version,
        ),
    )

    connection.executemany(
        """
        INSERT INTO topic_segment_parts (
            topic_segment_id,
            part_id,
            position
        )
        VALUES (?, ?, ?)
        """,
        [
            (
                topic_segment.id,
                part_id,
                position,
            )
            for position, part_id in enumerate(topic_segment.source_part_ids)
        ],
    )

    connection.executemany(
        """
        INSERT INTO topic_segment_reaction_matches (
            topic_segment_id,
            reaction_match_id,
            position
        )
        VALUES (?, ?, ?)
        """,
        [
            (
                topic_segment.id,
                reaction_match_id,
                position,
            )
            for position, reaction_match_id in enumerate(
                topic_segment.reaction_match_ids
            )
        ],
    )

    connection.executemany(
        """
        INSERT INTO topic_segment_transcripts (
            topic_segment_id,
            transcript_segment_id,
            position
        )
        VALUES (?, ?, ?)
        """,
        [
            (
                topic_segment.id,
                transcript_segment_id,
                position,
            )
            for position, transcript_segment_id in enumerate(
                topic_segment.transcript_segment_ids
            )
        ],
    )

    connection.executemany(
        """
        INSERT INTO topic_segment_keywords (
            topic_segment_id,
            keyword,
            position
        )
        VALUES (?, ?, ?)
        """,
        [
            (
                topic_segment.id,
                keyword,
                position,
            )
            for position, keyword in enumerate(topic_segment.keywords)
        ],
    )

    connection.executemany(
        """
        INSERT INTO topic_segment_entities (
            topic_segment_id,
            entity,
            position
        )
        VALUES (?, ?, ?)
        """,
        [
            (
                topic_segment.id,
                entity,
                position,
            )
            for position, entity in enumerate(topic_segment.entities)
        ],
    )


def insert_topic_segment(
    connection: sqlite3.Connection,
    topic_segment: TopicSegment,
) -> None:
    _validate_topic_segment(
        connection,
        topic_segment,
    )

    with connection:
        _insert_rows(
            connection,
            topic_segment,
        )


def get_topic_segment_by_id(
    connection: sqlite3.Connection,
    topic_segment_id: str,
) -> TopicSegment | None:
    row = connection.execute(
        """
        SELECT
            id,
            stream_id,
            start_ms,
            end_ms,
            topic_type,
            title,
            summary,
            salience_score,
            confidence,
            analyzer_version
        FROM topic_segments
        WHERE id = ?
        """,
        (topic_segment_id,),
    ).fetchone()

    if row is None:
        return None

    part_rows = connection.execute(
        """
        SELECT part_id
        FROM topic_segment_parts
        WHERE topic_segment_id = ?
        ORDER BY position ASC
        """,
        (topic_segment_id,),
    ).fetchall()

    reaction_match_rows = connection.execute(
        """
        SELECT reaction_match_id
        FROM topic_segment_reaction_matches
        WHERE topic_segment_id = ?
        ORDER BY position ASC
        """,
        (topic_segment_id,),
    ).fetchall()

    transcript_rows = connection.execute(
        """
        SELECT transcript_segment_id
        FROM topic_segment_transcripts
        WHERE topic_segment_id = ?
        ORDER BY position ASC
        """,
        (topic_segment_id,),
    ).fetchall()

    keyword_rows = connection.execute(
        """
        SELECT keyword
        FROM topic_segment_keywords
        WHERE topic_segment_id = ?
        ORDER BY position ASC
        """,
        (topic_segment_id,),
    ).fetchall()

    entity_rows = connection.execute(
        """
        SELECT entity
        FROM topic_segment_entities
        WHERE topic_segment_id = ?
        ORDER BY position ASC
        """,
        (topic_segment_id,),
    ).fetchall()

    return TopicSegment(
        id=row[0],
        stream_id=row[1],
        source_part_ids=[item[0] for item in part_rows],
        reaction_match_ids=[item[0] for item in reaction_match_rows],
        start_ms=row[2],
        end_ms=row[3],
        topic_type=row[4],
        title=row[5],
        summary=row[6],
        keywords=[item[0] for item in keyword_rows],
        entities=[item[0] for item in entity_rows],
        transcript_segment_ids=[item[0] for item in transcript_rows],
        salience_score=row[7],
        confidence=row[8],
        analyzer_version=row[9],
    )


def list_topic_segments_by_stream(
    connection: sqlite3.Connection,
    *,
    stream_id: str,
) -> list[TopicSegment]:
    rows = connection.execute(
        """
        SELECT id
        FROM topic_segments
        WHERE stream_id = ?
        ORDER BY
            start_ms ASC,
            end_ms ASC,
            id ASC
        """,
        (stream_id,),
    ).fetchall()

    results: list[TopicSegment] = []

    for row in rows:
        topic_segment = get_topic_segment_by_id(
            connection,
            row[0],
        )

        if topic_segment is not None:
            results.append(topic_segment)

    return results


def replace_topic_segments_for_stream(
    connection: sqlite3.Connection,
    *,
    stream_id: str,
    topic_segments: list[TopicSegment],
) -> None:
    seen_segment_ids: set[str] = set()
    seen_reaction_match_ids: set[str] = set()

    for topic_segment in topic_segments:
        if topic_segment.stream_id != stream_id:
            raise ValueError("all topic segments must belong " "to target stream")

        if topic_segment.id in seen_segment_ids:
            raise ValueError("duplicate topic segment id: " f"{topic_segment.id}")

        seen_segment_ids.add(topic_segment.id)

        for reaction_match_id in topic_segment.reaction_match_ids:
            if reaction_match_id in seen_reaction_match_ids:
                raise ValueError(
                    "reaction match appears in multiple "
                    "topic segments: "
                    f"{reaction_match_id}"
                )

            seen_reaction_match_ids.add(reaction_match_id)

        _validate_topic_segment(
            connection,
            topic_segment,
        )

    with connection:
        connection.execute(
            """
            DELETE FROM topic_segments
            WHERE stream_id = ?
            """,
            (stream_id,),
        )

        for topic_segment in topic_segments:
            _insert_rows(
                connection,
                topic_segment,
            )
