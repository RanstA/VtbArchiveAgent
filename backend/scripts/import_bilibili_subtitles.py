import argparse
from pathlib import Path

from app.domain.evidence.transcript_segment import (
    TranscriptSegment,
)
from app.ingestion.bilibili_client import (
    BilibiliClient,
)
from app.ingestion.bilibili_session import (
    BilibiliSessionStore,
)
from app.ingestion.bilibili_subtitle import (
    get_ai_chinese_subtitles,
)
from app.repository.database import (
    connect_db,
    init_db,
)
from app.repository.stream_part_repo import (
    list_stream_parts,
)
from app.repository.transcript_segment_repo import (
    insert_transcript_segments_batch,
)


def build_client() -> BilibiliClient:
    store = BilibiliSessionStore()
    session = store.load()

    if session is None:
        raise RuntimeError("No valid Bilibili session found.")

    client = BilibiliClient(
        sessdata=session.sessdata,
    )

    if not client.is_authenticated():
        raise RuntimeError("Bilibili session is no longer valid.")

    return client


def delete_bilibili_ai_transcripts(
    connection,
    *,
    stream_id: str,
    part_id: str,
) -> None:
    """
    删除当前 Part 已有的 Bilibili AI 字幕。

    这样脚本可以安全重复运行，
    不会不断插入重复 TranscriptSegment。
    """

    connection.execute(
        """
        DELETE FROM transcript_segments
        WHERE stream_id = ?
          AND part_id = ?
          AND source = 'bilibili_ai'
        """,
        (
            stream_id,
            part_id,
        ),
    )


def import_stream_subtitles(
    *,
    connection,
    client: BilibiliClient,
    stream_id: str,
) -> None:
    parts = list_stream_parts(
        connection=connection,
        stream_id=stream_id,
    )

    if not parts:
        raise RuntimeError(f"No StreamPart found: {stream_id}")

    print()
    print("=" * 72)
    print("Bilibili Subtitle Import")
    print("=" * 72)
    print("Stream ID:", stream_id)
    print("Parts:", len(parts))

    total_segments = 0
    imported_parts = 0
    skipped_parts = 0

    for index, part in enumerate(
        parts,
        start=1,
    ):
        part_id = part["part_id"]
        bvid = part["bvid"]
        cid = part["cid"]

        print()
        print("-" * 72)
        print(
            f"[{index}/{len(parts)}]",
            part_id,
        )
        print("BVID:", bvid)
        print("CID:", cid)

        if not bvid or not cid:
            print("SKIP: missing bvid or cid")
            skipped_parts += 1
            continue

        subtitles = get_ai_chinese_subtitles(
            client,
            bvid=str(bvid),
            cid=str(cid),
        )

        print(
            "Subtitle rows:",
            len(subtitles),
        )

        if not subtitles:
            print("SKIP: no ai-zh subtitle")
            skipped_parts += 1
            continue

        segments = [
            TranscriptSegment(
                stream_id=stream_id,
                part_id=part_id,
                start_ms=item.start_ms,
                end_ms=item.end_ms,
                raw_text=item.text,
                text=item.text,
                source="bilibili_ai",
            )
            for item in subtitles
        ]

        try:
            with connection:
                delete_bilibili_ai_transcripts(
                    connection,
                    stream_id=stream_id,
                    part_id=part_id,
                )

                insert_transcript_segments_batch(
                    connection,
                    segments,
                )

        except Exception:
            print(
                "FAILED while writing:",
                part_id,
            )
            raise

        print(
            "Inserted:",
            len(segments),
        )

        print(
            "Range:",
            f"{segments[0].start_ms} ms",
            "->",
            f"{segments[-1].end_ms} ms",
        )

        imported_parts += 1
        total_segments += len(segments)

    print()
    print("=" * 72)
    print("Import finished")
    print("=" * 72)
    print(
        "Imported parts:",
        imported_parts,
    )
    print(
        "Skipped parts:",
        skipped_parts,
    )
    print(
        "Transcript segments:",
        total_segments,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Import Bilibili AI Chinese " "subtitles into transcript_segments."
        )
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=Path("vtuber_archive.db"),
    )

    parser.add_argument(
        "--stream-id",
        required=True,
    )

    args = parser.parse_args()

    client = build_client()

    connection = connect_db(args.db)

    try:
        init_db(connection)

        import_stream_subtitles(
            connection=connection,
            client=client,
            stream_id=args.stream_id,
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
