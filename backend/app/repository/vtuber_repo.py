import sqlite3

from app.domain.source.vtuber import (
    Vtuber,
)


def insert_vtuber(
    connection: sqlite3.Connection,
    vtuber: Vtuber,
) -> None:
    connection.execute(
        """
        INSERT INTO vtubers (
            id,
            display_name
        )
        VALUES (?, ?)

        ON CONFLICT(id)
        DO UPDATE SET
            display_name = excluded.display_name
        """,
        (
            vtuber.id,
            vtuber.display_name,
        ),
    )


def get_vtuber(
    connection: sqlite3.Connection,
    vtuber_id: str,
) -> Vtuber | None:
    row = connection.execute(
        """
        SELECT
            id,
            display_name
        FROM vtubers
        WHERE id = ?
        """,
        (vtuber_id,),
    ).fetchone()

    if row is None:
        return None

    return Vtuber(
        id=row[0],
        display_name=row[1],
    )


def list_vtubers(
    connection: sqlite3.Connection,
) -> list[Vtuber]:
    rows = connection.execute(
        """
        SELECT
            id,
            display_name
        FROM vtubers
        ORDER BY display_name ASC
        """
    ).fetchall()

    return [
        Vtuber(
            id=row[0],
            display_name=row[1],
        )
        for row in rows
    ]
