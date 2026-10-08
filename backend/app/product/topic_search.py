import sqlite3

from app.product.search import SearchHit


def search_topics(
    connection: sqlite3.Connection,
    query: str,
    vtuber_id: str | None = None,
    limit: int = 5,
) -> list[SearchHit]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    term = query.strip()

    if not term:
        return []

    rows = connection.execute(
        """
        WITH candidates AS (
            SELECT
                t.id,
                t.stream_id,
                t.start_ms,
                t.end_ms,
                t.title,
                t.summary,
                s.live_time,

                (
                    CASE WHEN instr(t.title, ?) > 0
                        THEN 5 ELSE 0 END
                    +
                    CASE WHEN instr(t.summary, ?) > 0
                        THEN 2 ELSE 0 END
                    +
                    CASE WHEN EXISTS (
                        SELECT 1
                        FROM topic_segment_keywords k
                        WHERE k.topic_segment_id = t.id
                          AND instr(k.keyword, ?) > 0
                    ) THEN 4 ELSE 0 END
                    +
                    CASE WHEN EXISTS (
                        SELECT 1
                        FROM topic_segment_entities e
                        WHERE e.topic_segment_id = t.id
                          AND instr(e.entity, ?) > 0
                    ) THEN 4 ELSE 0 END
                ) AS score

            FROM topic_segments t
            JOIN streams s ON s.id = t.stream_id
            WHERE (? IS NULL OR s.vtuber_id = ?)
        )

        SELECT
            id, stream_id, start_ms, end_ms,
            title, summary, score
        FROM candidates
        WHERE score > 0
        ORDER BY score DESC, live_time DESC, start_ms ASC
        LIMIT ?
        """,
        (
            term,
            term,
            term,
            term,
            vtuber_id,
            vtuber_id,
            limit,
        ),
    ).fetchall()

    return [
        SearchHit(
            stream_id=row[1],
            topic_segment_id=row[0],
            start_ms=row[2],
            end_ms=row[3],
            title=row[4],
            snippet=row[5],
            score=float(row[6]),
            evidence_ids=None,
        )
        for row in rows
    ]
