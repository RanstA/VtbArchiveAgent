import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from app.domain.stream import Stream
from app.domain.vtuber import Vtuber
from app.ingestion.csv_loader import load_streams
from app.ingestion.local_source import LocalSource
from app.ingestion.persist import (
    persist_archive_bundle,
)
from app.repository.database import (
    connect_db,
    init_db,
)


DEFAULT_DB_PATH = Path(
    "vtuber_archive.db"
)

DEFAULT_REPORT_PATH = Path(
    "import_report.json"
)


def import_stream(
    connection: sqlite3.Connection,
    stream: Stream,
    *,
    vtuber: Vtuber,
    archive_root: Path,
    layout: str = "auto",
) -> dict:
    """
    导入单场本地 Stream。

    orchestration：

        Stream
        -> LocalSource
        -> ArchiveBundle
        -> persist_archive_bundle
        -> SQLite

    LocalSource 负责读取本地 Archive。

    persist_archive_bundle 负责
    完整数据库事务。
    """

    result = {
        "stream_id": stream.id,
        "vtuber_id": stream.vtuber_id,
        "title": stream.title,
        "status": None,
        "layout": None,
        "matched_path": None,
        "parts": 0,
        "danmaku": 0,
        "error": None,
    }

    try:
        source = LocalSource(
            stream=stream,
            archive_root=archive_root,
            vtuber=vtuber,
            layout=layout,
        )

        bundle = source.load()

        persist_archive_bundle(
            connection=connection,
            bundle=bundle,
        )

        result["layout"] = (
            bundle.source_metadata.get(
                "layout"
            )
        )

        result["matched_path"] = (
            bundle.source_metadata.get(
                "matched_path"
            )
        )

        result["parts"] = len(
            bundle.parts
        )

        result["danmaku"] = len(
            bundle.danmaku
        )

        if bundle.parts:
            result["status"] = (
                "imported"
            )
        else:
            result["status"] = (
                "metadata_only"
            )

        return result

    except Exception as exc:
        # persist_archive_bundle 本身已经保证
        # 事务失败时 rollback。
        #
        # 这里额外清理可能残留的事务状态，
        # 保证后面的 Stream 可以继续导入。
        if connection.in_transaction:
            connection.rollback()

        result["status"] = "failed"

        result["error"] = str(
            exc
        )

        return result


def write_report(
    results: list[dict],
    report_path: Path,
) -> None:
    report = {
        "generated_at": (
            datetime.now()
            .isoformat()
        ),
        "total": len(
            results
        ),
        "imported": sum(
            1
            for item in results
            if (
                item["status"]
                == "imported"
            )
        ),
        "metadata_only": sum(
            1
            for item in results
            if (
                item["status"]
                == "metadata_only"
            )
        ),
        "failed": sum(
            1
            for item in results
            if (
                item["status"]
                == "failed"
            )
        ),
        "total_parts": sum(
            item["parts"]
            for item in results
        ),
        "total_danmaku": sum(
            item["danmaku"]
            for item in results
        ),
        "streams": results,
    }

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def print_summary(
    results: list[dict],
    report_path: Path,
) -> None:
    imported = [
        item
        for item in results
        if (
            item["status"]
            == "imported"
        )
    ]

    metadata_only = [
        item
        for item in results
        if (
            item["status"]
            == "metadata_only"
        )
    ]

    failed = [
        item
        for item in results
        if (
            item["status"]
            == "failed"
        )
    ]

    print()
    print("=" * 60)
    print("导入完成")
    print("=" * 60)

    print(
        "Stream 总数:",
        len(results),
    )

    print(
        "完整导入:",
        len(imported),
    )

    print(
        "仅元数据:",
        len(metadata_only),
    )

    print(
        "失败:",
        len(failed),
    )

    print(
        "Part 总数:",
        sum(
            item["parts"]
            for item in results
        ),
    )

    print(
        "Danmaku 总数:",
        sum(
            item["danmaku"]
            for item in results
        ),
    )

    if metadata_only:
        print()
        print(
            "=== 仅元数据项 ==="
        )

        for item in metadata_only:
            print()
            print(
                item["title"]
            )

    if failed:
        print()
        print(
            "=== 失败项 ==="
        )

        for item in failed:
            print()
            print(
                item["title"]
            )

            print(
                "原因:",
                item["error"],
            )

    print()

    print(
        "详细报告:",
        report_path.resolve(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Import a local VTuber archive "
            "into SQLite."
        )
    )

    parser.add_argument(
        "--archive-root",
        type=Path,
        required=True,
        help=(
            "本地主播 Archive 根目录"
        ),
    )

    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help=(
            "Stream 元数据 CSV。"
            "默认使用 "
            "<archive-root>/录播完整检查.csv"
        ),
    )

    parser.add_argument(
        "--vtuber-id",
        required=True,
        help=(
            "系统内部稳定 VTuber ID，"
            "例如 mikoto / aza"
        ),
    )

    parser.add_argument(
        "--vtuber-name",
        required=True,
        help=(
            "VTuber 当前显示名称"
        ),
    )

    parser.add_argument(
        "--layout",
        choices=[
            "auto",
            "nested",
            "flat",
        ],
        default="auto",
        help=(
            "本地 Archive 布局"
        ),
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=(
            "目标 SQLite 数据库"
        ),
    )

    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help=(
            "导入报告输出路径"
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "仅处理前 N 条，"
            "用于 smoke test"
        ),
    )

    args = parser.parse_args()

    if (
        args.limit is not None
        and args.limit < 1
    ):
        parser.error(
            "--limit must be >= 1"
        )

    archive_root = (
        args.archive_root
        .expanduser()
        .resolve()
    )

    csv_path = (
        args.csv.expanduser().resolve()
        if args.csv is not None
        else (
            archive_root
            / "录播完整检查.csv"
        )
    )

    db_path = (
        args.db
        .expanduser()
        .resolve()
    )

    report_path = (
        args.report
        .expanduser()
        .resolve()
    )

    if not archive_root.exists():
        raise FileNotFoundError(
            "Archive root does not exist: "
            f"{archive_root}"
        )

    if not archive_root.is_dir():
        raise NotADirectoryError(
            "Archive root is not a directory: "
            f"{archive_root}"
        )

    if not csv_path.exists():
        raise FileNotFoundError(
            f"CSV does not exist: "
            f"{csv_path}"
        )

    if not csv_path.is_file():
        raise FileNotFoundError(
            f"CSV is not a file: "
            f"{csv_path}"
        )

    vtuber_id = (
        args.vtuber_id.strip()
    )

    vtuber_name = (
        args.vtuber_name.strip()
    )

    if not vtuber_id:
        parser.error(
            "--vtuber-id cannot be empty"
        )

    if not vtuber_name:
        parser.error(
            "--vtuber-name cannot be empty"
        )

    vtuber = Vtuber(
        id=vtuber_id,
        display_name=vtuber_name,
    )

    print()
    print("VTuber:")
    print(
        f"{vtuber.display_name} "
        f"({vtuber.id})"
    )

    print()
    print("Archive Root:")
    print(
        archive_root
    )

    print()
    print("CSV:")
    print(
        csv_path
    )

    print()
    print("Layout:")
    print(
        args.layout
    )

    print()
    print("Database:")
    print(
        db_path
    )

    streams = load_streams(
        csv_path,
        vtuber_id=vtuber.id,
    )

    if args.limit is not None:
        streams = streams[
            : args.limit
        ]

    print()
    print(
        "准备处理 "
        f"{len(streams)} "
        "个 Stream"
    )

    connection = connect_db(
        db_path
    )

    results: list[
        dict
    ] = []

    try:
        init_db(
            connection
        )

        total = len(
            streams
        )

        for index, stream in enumerate(
            streams,
            start=1,
        ):
            print()

            print(
                f"[{index}/{total}] "
                f"{stream.title}"
            )

            result = import_stream(
                connection=connection,
                stream=stream,
                vtuber=vtuber,
                archive_root=(
                    archive_root
                ),
                layout=args.layout,
            )

            results.append(
                result
            )

            if (
                result["status"]
                == "imported"
            ):
                print(
                    "  imported | "
                    f"layout="
                    f"{result['layout']} | "
                    f"parts="
                    f"{result['parts']} | "
                    f"danmaku="
                    f"{result['danmaku']}"
                )

            elif (
                result["status"]
                == "metadata_only"
            ):
                print(
                    "  metadata_only | "
                    f"layout="
                    f"{result['layout']}"
                )

            else:
                print(
                    "  FAILED |",
                    result["error"],
                )

    finally:
        connection.close()

    write_report(
        results=results,
        report_path=report_path,
    )

    print_summary(
        results=results,
        report_path=report_path,
    )


if __name__ == "__main__":
    main()