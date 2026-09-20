import sqlite3

from app.domain.vtuber import (
    Vtuber,
    VtuberSource,
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


def insert_vtuber_source(
    connection: sqlite3.Connection,
    vtuber_source: VtuberSource,
) -> None:
    connection.execute(
        """
        INSERT INTO vtuber_sources (
            vtuber_id,
            source,
            external_id,
            display_name
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(
            vtuber_id,
            source
        )
        DO UPDATE SET
            external_id = excluded.external_id,
            display_name = excluded.display_name
        """,
        (
            vtuber_source.vtuber_id,
            vtuber_source.source,
            vtuber_source.external_id,
            vtuber_source.display_name,
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


def list_vtuber_sources(
    connection: sqlite3.Connection,
    vtuber_id: str,
) -> list[VtuberSource]:
    rows = connection.execute(
        """
        SELECT
            vtuber_id,
            source,
            external_id,
            display_name
        FROM vtuber_sources
        WHERE vtuber_id = ?
        ORDER BY source ASC
        """,
        (vtuber_id,),
    ).fetchall()

    return [
        VtuberSource(
            vtuber_id=row[0],
            source=row[1],
            external_id=row[2],
            display_name=row[3],
        )
        for row in rows
    ]