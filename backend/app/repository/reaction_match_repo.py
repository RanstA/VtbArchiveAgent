import sqlite3

from app.domain.pipeline.reaction_match import (
    ReactionMatch,
)


def _validate_reaction_match(
    connection: sqlite3.Connection,
    reaction_match: ReactionMatch,
) -> None:
    """
    验证 ReactionMatch 引用的所有 Evidence
    都属于同一个 StreamPart。
    """

    highlight_row = connection.execute(
        """
        SELECT
            stream_id,
            part_id
        FROM highlights
        WHERE id = ?
        """,
        (reaction_match.highlight_id,),
    ).fetchone()

    if highlight_row is None:
        raise ValueError("highlight does not exist: " f"{reaction_match.highlight_id}")

    if (
        highlight_row[0] != reaction_match.stream_id
        or highlight_row[1] != reaction_match.part_id
    ):
        raise ValueError("highlight does not belong " "to reaction_match StreamPart")

    if len(reaction_match.transcript_segment_ids) != len(
        set(reaction_match.transcript_segment_ids)
    ):
        raise ValueError("duplicate transcript_segment_ids")

    if len(reaction_match.danmaku_ids) != len(set(reaction_match.danmaku_ids)):
        raise ValueError("duplicate danmaku_ids")

    for transcript_id in reaction_match.transcript_segment_ids:
        row = connection.execute(
            """
            SELECT
                stream_id,
                part_id
            FROM transcript_segments
            WHERE id = ?
            """,
            (transcript_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                "transcript segment " "does not exist: " f"{transcript_id}"
            )

        if row[0] != reaction_match.stream_id or row[1] != reaction_match.part_id:
            raise ValueError(
                "transcript segment does " "not belong to reaction_match " "StreamPart"
            )

    for danmaku_id in reaction_match.danmaku_ids:
        row = connection.execute(
            """
            SELECT
                sp.stream_id,
                sp.part_id
            FROM danmaku AS d
            JOIN stream_parts AS sp
                ON sp.id = d.stream_part_id
            WHERE d.id = ?
            """,
            (danmaku_id,),
        ).fetchone()

        if row is None:
            raise ValueError("danmaku does not exist: " f"{danmaku_id}")

        if row[0] != reaction_match.stream_id or row[1] != reaction_match.part_id:
            raise ValueError("danmaku does not belong " "to reaction_match StreamPart")


def _insert_rows(
    connection: sqlite3.Connection,
    reaction_match: ReactionMatch,
) -> None:
    connection.execute(
        """
        INSERT INTO reaction_matches (
            id,
            stream_id,
            part_id,
            highlight_id,
            matcher_version
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            reaction_match.id,
            reaction_match.stream_id,
            reaction_match.part_id,
            reaction_match.highlight_id,
            reaction_match.matcher_version,
        ),
    )

    connection.executemany(
        """
        INSERT INTO reaction_match_transcripts (
            reaction_match_id,
            transcript_segment_id,
            position
        )
        VALUES (?, ?, ?)
        """,
        [
            (
                reaction_match.id,
                transcript_id,
                position,
            )
            for position, transcript_id in enumerate(
                reaction_match.transcript_segment_ids
            )
        ],
    )

    connection.executemany(
        """
        INSERT INTO reaction_match_danmaku (
            reaction_match_id,
            danmaku_id,
            position
        )
        VALUES (?, ?, ?)
        """,
        [
            (
                reaction_match.id,
                danmaku_id,
                position,
            )
            for position, danmaku_id in enumerate(reaction_match.danmaku_ids)
        ],
    )


def insert_reaction_match(
    connection: sqlite3.Connection,
    reaction_match: ReactionMatch,
) -> None:
    _validate_reaction_match(
        connection,
        reaction_match,
    )

    with connection:
        _insert_rows(
            connection,
            reaction_match,
        )


def get_reaction_match_by_id(
    connection: sqlite3.Connection,
    reaction_match_id: str,
) -> ReactionMatch | None:
    row = connection.execute(
        """
        SELECT
            id,
            stream_id,
            part_id,
            highlight_id,
            matcher_version
        FROM reaction_matches
        WHERE id = ?
        """,
        (reaction_match_id,),
    ).fetchone()

    if row is None:
        return None

    transcript_rows = connection.execute(
        """
        SELECT transcript_segment_id
        FROM reaction_match_transcripts
        WHERE reaction_match_id = ?
        ORDER BY position ASC
        """,
        (reaction_match_id,),
    ).fetchall()

    danmaku_rows = connection.execute(
        """
        SELECT danmaku_id
        FROM reaction_match_danmaku
        WHERE reaction_match_id = ?
        ORDER BY position ASC
        """,
        (reaction_match_id,),
    ).fetchall()

    return ReactionMatch(
        id=row[0],
        stream_id=row[1],
        part_id=row[2],
        highlight_id=row[3],
        transcript_segment_ids=[item[0] for item in transcript_rows],
        danmaku_ids=[int(item[0]) for item in danmaku_rows],
        matcher_version=row[4],
    )


def list_reaction_matches_by_stream(
    connection: sqlite3.Connection,
    *,
    stream_id: str,
) -> list[ReactionMatch]:
    rows = connection.execute(
        """
        SELECT rm.id
        FROM reaction_matches AS rm

        JOIN stream_parts AS sp
            ON sp.stream_id = rm.stream_id
            AND sp.part_id = rm.part_id

        JOIN highlights AS h
            ON h.id = rm.highlight_id

        WHERE rm.stream_id = ?

        ORDER BY
            sp.start_offset_ms ASC,
            h.start_ms ASC
        """,
        (stream_id,),
    ).fetchall()

    results: list[ReactionMatch] = []

    for row in rows:
        reaction_match = get_reaction_match_by_id(
            connection,
            row[0],
        )

        if reaction_match is not None:
            results.append(reaction_match)

    return results


def replace_reaction_matches_for_stream(
    connection: sqlite3.Connection,
    *,
    stream_id: str,
    reaction_matches: list[ReactionMatch],
) -> None:
    for reaction_match in reaction_matches:
        if reaction_match.stream_id != stream_id:
            raise ValueError("all reaction matches must " "belong to target stream")

        _validate_reaction_match(
            connection,
            reaction_match,
        )

    with connection:
        connection.execute(
            """
            DELETE FROM reaction_matches
            WHERE stream_id = ?
            """,
            (stream_id,),
        )

        for reaction_match in reaction_matches:
            _insert_rows(
                connection,
                reaction_match,
            )
