import json
import sqlite3

from app.domain.event import Event


def upsert_event(connection: sqlite3.Connection, event: Event) -> None:
    """
    写入或更新一个 Unified Event。

    Event ID 由 stream + 时间边界稳定生成，
    因此重新 Semanticize 同一事件时，
    可以更新语义字段而不改变身份。
    """

    with connection:
        connection.execute(
            """
            INSERT INTO events (
                id,
                stream_id,

                source_part_ids,

                start_ms,
                end_ms,
                anchor_ms,

                source_highlight_ids,

                title,
                summary,

                keywords,
                entities,

                semantic_text,

                salience_score,

                segmenter_version,
                semanticizer_version
            )
            VALUES (
                ?, ?,
                ?,
                ?, ?, ?,
                ?,
                ?, ?,
                ?, ?,
                ?,
                ?,
                ?, ?
            )

            ON CONFLICT(id)
            DO UPDATE SET
                stream_id = excluded.stream_id,
                source_part_ids = excluded.source_part_ids,

                start_ms = excluded.start_ms,
                end_ms = excluded.end_ms,
                anchor_ms = excluded.anchor_ms,

                source_highlight_ids = excluded.source_highlight_ids,

                title = excluded.title,
                summary = excluded.summary,

                keywords = excluded.keywords,
                entities = excluded.entities,

                semantic_text = excluded.semantic_text,

                salience_score = excluded.salience_score,

                segmenter_version = excluded.segmenter_version,
                semanticizer_version = excluded.semanticizer_version
            """,
            _event_to_row(event),
        )


def get_event_by_id(
    connection: sqlite3.Connection,
    event_id: str,
) -> Event | None:
    row = connection.execute(
        """
        SELECT
            id,
            stream_id,

            source_part_ids,

            start_ms,
            end_ms,
            anchor_ms,

            source_highlight_ids,

            title,
            summary,

            keywords,
            entities,

            semantic_text,

            salience_score,

            segmenter_version,
            semanticizer_version

        FROM events

        WHERE id = ?
        """,
        (event_id,),
    ).fetchone()

    if row is None:
        return None

    return _row_to_event(row)

def list_events_by_stream(
    connection: sqlite3.Connection,
    stream_id: str,
) -> list[Event]:
    rows = connection.execute(
        """
        SELECT
            id,
            stream_id,

            source_part_ids,

            start_ms,
            end_ms,
            anchor_ms,

            source_highlight_ids,

            title,
            summary,

            keywords,
            entities,

            semantic_text,

            salience_score,

            segmenter_version,
            semanticizer_version

        FROM events

        WHERE stream_id = ?

        ORDER BY
            start_ms ASC,
            end_ms ASC
        """,
        (
            stream_id,
        ),
    ).fetchall()


    return [
        _row_to_event(
            row
        )
        for row in rows
    ]

def _event_to_row(
    event: Event,
) -> tuple:
    return (
        event.id,
        event.stream_id,
        json.dumps(event.source_part_ids, ensure_ascii=False),
        event.start_ms,
        event.end_ms,
        event.anchor_ms,
        json.dumps(event.source_highlight_ids, ensure_ascii=False),
        event.title,
        event.summary,
        json.dumps(event.keywords, ensure_ascii=False),
        json.dumps(event.entities, ensure_ascii=False),
        event.semantic_text,
        event.salience_score,
        event.segmenter_version,
        event.semanticizer_version,
    )


def _row_to_event(
    row: tuple,
) -> Event:
    return Event(
        id=row[0],
        stream_id=row[1],
        source_part_ids=json.loads(row[2]),
        start_ms=row[3],
        end_ms=row[4],
        anchor_ms=row[5],
        source_highlight_ids=json.loads(row[6]),
        title=row[7],
        summary=row[8],
        keywords=json.loads(row[9]),
        entities=json.loads(row[10]),
        semantic_text=row[11],
        salience_score=row[12],
        segmenter_version=row[13],
        semanticizer_version=row[14],
    )
