import argparse
import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from app.config.settings import settings
from app.ingestion.archive_scanner import scan_stream_directory
from app.ingestion.ass_parser import parse_ass
from app.ingestion.csv_loader import load_streams
from app.repository.database import connect_db, init_db
from app.repository.danmaku_repo import insert_danmaku_batch
from app.repository.stream_part_repo import (
    delete_stream_parts,
    insert_stream_part,
)
from app.repository.stream_repo import insert_stream


DB_PATH = Path("vtuber_archive.db")

ARCHIVE_ROOT = settings.archive_data_root

CSV_PATH = ARCHIVE_ROOT / "录播完整检查.csv"

REPORT_PATH = Path("import_report.json")


WINDOWS_FORBIDDEN = re.compile(r'[<>:"/\\|?*]')


def build_directory_index(
    archive_root: Path,
) -> dict[str, list[Path]]:
    """
    扫描整个归档目录。

    key:
        文件夹名称

    value:
        所有同名目录
    """
    index: dict[str, list[Path]] = {}

    for root, dirs, _ in os.walk(archive_root):
        root_path = Path(root)

        for directory_name in dirs:
            directory_path = root_path / directory_name

            index.setdefault(
                directory_name,
                [],
            ).append(directory_path)

    return index


def normalize_directory_name(
    value: str,
) -> str:
    """
    仅用于目录匹配，不修改数据库里的原始标题。

    处理：
    1. Unicode 兼容归一化
    2. 删除 Windows 文件名禁止字符
    3. 去除首尾空白

    例如：
        CSV:  嗯?
        Folder: 嗯

    或：
        CSV:  *
        Folder: ＊

    可以归一化到同一种形式。
    """
    value = unicodedata.normalize(
        "NFKC",
        value,
    )

    value = WINDOWS_FORBIDDEN.sub(
        "",
        value,
    )

    return value.strip()


def expected_month_directory(
    stream,
) -> str:
    """
    根据直播时间推导它理论上所属的月份目录。

    例如：
        2023-10-04
        ->
        2023年10月录播
    """
    return (
        f"{stream.live_time.year}年"
        f"{stream.live_time.month}月录播"
    )


def resolve_stream_directory(
    stream,
    directory_index: dict[str, list[Path]],
) -> Path | None:
    """
    按确定性规则解析 Stream 对应的本地录播目录。

    优先级：

    1. 标题完全匹配，并且只有一个目录
    2. 标题完全匹配但存在多个目录时，
       优先直播年月对应的月份目录
    3. 完全匹配失败时，
       在正确月份内进行文件名安全归一化后的精确匹配
    4. 仍然无法唯一确定时返回 None 或抛出异常

    不做 fuzzy matching。
    """
    expected_month = expected_month_directory(
        stream
    )

    # --------------------------------
    # 1. 标题完全匹配
    # --------------------------------

    exact_candidates = directory_index.get(
        stream.title,
        [],
    )

    if len(exact_candidates) == 1:
        return exact_candidates[0]

    # --------------------------------
    # 2. 完全匹配出现多个目录
    #
    # 根据直播年月选择正确月份
    # --------------------------------

    if len(exact_candidates) > 1:
        month_candidates = [
            path
            for path in exact_candidates
            if path.parent.name == expected_month
        ]

        if len(month_candidates) == 1:
            return month_candidates[0]

        if len(month_candidates) > 1:
            raise RuntimeError(
                "正确月份内仍存在多个同名录播目录: "
                + " | ".join(
                    str(path)
                    for path in month_candidates
                )
            )

        raise RuntimeError(
            "找到多个同名录播目录，"
            "但没有唯一正确月份目录: "
            + " | ".join(
                str(path)
                for path in exact_candidates
            )
        )

    # --------------------------------
    # 3. 完全匹配不到
    #
    # 处理 Windows 非法字符：
    #
    # ? * : 等字符无法直接出现在 Windows 文件名里
    #
    # 只在正确月份中进行归一化后的精确匹配
    # --------------------------------

    normalized_title = normalize_directory_name(
        stream.title
    )

    normalized_candidates: list[Path] = []

    for directory_name, paths in directory_index.items():
        normalized_directory_name = normalize_directory_name(
            directory_name
        )

        if normalized_directory_name != normalized_title:
            continue

        for path in paths:
            if path.parent.name == expected_month:
                normalized_candidates.append(
                    path
                )

    if len(normalized_candidates) == 1:
        return normalized_candidates[0]

    if len(normalized_candidates) > 1:
        raise RuntimeError(
            "文件名归一化后仍匹配到多个目录: "
            + " | ".join(
                str(path)
                for path in normalized_candidates
            )
        )

    # --------------------------------
    # 4. 仍然没有找到
    # --------------------------------

    return None


def import_stream(
    connection,
    stream,
    directory_index: dict[str, list[Path]],
) -> dict:
    """
    导入单场 Stream。

    每场 Stream 独立事务。
    """
    result = {
        "stream_id": stream.id,
        "title": stream.title,
        "status": None,
        "directory": None,
        "parts": 0,
        "danmaku": 0,
        "error": None,
    }

    try:
        # --------------------------------
        # 1. 写 Stream 元数据 + BV
        # --------------------------------

        insert_stream(
            connection=connection,
            stream=stream,
        )

        # --------------------------------
        # 2. 解析本地目录
        # --------------------------------

        stream_directory = resolve_stream_directory(
            stream=stream,
            directory_index=directory_index,
        )

        # 找不到本地录播：
        # 仍然保留 CSV 元数据
        if stream_directory is None:
            connection.commit()

            result["status"] = "metadata_only"

            return result

        result["directory"] = str(
            stream_directory
        )

        # --------------------------------
        # 3. 幂等重导
        #
        # 删除旧 Part。
        #
        # danmaku 会通过 ON DELETE CASCADE
        # 自动删除。
        #
        # 如果后面失败，
        # rollback 会撤销这里的删除。
        # --------------------------------

        delete_stream_parts(
            connection=connection,
            stream_id=stream.id,
        )

        # --------------------------------
        # 4. 扫描 Part
        # --------------------------------

        parts = scan_stream_directory(
            directory=stream_directory,
            stream_id=stream.id,
        )

        total_danmaku = 0

        # --------------------------------
        # 5. 导入 Part + Danmaku
        # --------------------------------

        for part in parts:
            stream_part_id = insert_stream_part(
                connection=connection,
                part=part,
            )

            if part.danmaku_path is None:
                continue

            danmaku = parse_ass(
                path=Path(part.danmaku_path),
                stream_id=stream.id,
                part_id=part.part_id,
            )

            insert_danmaku_batch(
                connection=connection,
                stream_part_id=stream_part_id,
                danmaku=danmaku,
            )

            total_danmaku += len(danmaku)

        # --------------------------------
        # 6. 单 Stream 全部成功才提交
        # --------------------------------

        connection.commit()

        result["status"] = "imported"
        result["parts"] = len(parts)
        result["danmaku"] = total_danmaku

        return result

    except Exception as exc:
        # 当前 Stream 失败，
        # 不影响其他 Stream。
        connection.rollback()

        result["status"] = "failed"
        result["error"] = str(exc)

        return result


def write_report(
    results: list[dict],
) -> None:
    report = {
        "generated_at": datetime.now().isoformat(),
        "total": len(results),
        "imported": sum(
            1
            for item in results
            if item["status"] == "imported"
        ),
        "metadata_only": sum(
            1
            for item in results
            if item["status"] == "metadata_only"
        ),
        "failed": sum(
            1
            for item in results
            if item["status"] == "failed"
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

    REPORT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def print_summary(
    results: list[dict],
) -> None:
    imported = [
        item
        for item in results
        if item["status"] == "imported"
    ]

    metadata_only = [
        item
        for item in results
        if item["status"] == "metadata_only"
    ]

    failed = [
        item
        for item in results
        if item["status"] == "failed"
    ]

    print()
    print("=" * 60)
    print("导入完成")
    print("=" * 60)

    print("Stream 总数:", len(results))
    print("完整导入:", len(imported))
    print("仅元数据:", len(metadata_only))
    print("失败:", len(failed))

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
        print("=== 仅元数据项 ===")

        for item in metadata_only:
            print()
            print(item["title"])

    if failed:
        print()
        print("=== 失败项 ===")

        for item in failed:
            print()
            print(item["title"])
            print(
                "原因:",
                item["error"],
            )

    print()
    print(
        "详细报告:",
        REPORT_PATH.resolve(),
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="仅导入前 N 条，用于测试",
    )

    args = parser.parse_args()

    print("Archive Root:")
    print(ARCHIVE_ROOT)

    print()
    print("CSV:")
    print(CSV_PATH)

    # --------------------------------
    # 基础路径检查
    # --------------------------------

    if not ARCHIVE_ROOT.exists():
        raise FileNotFoundError(
            f"归档根目录不存在: {ARCHIVE_ROOT}"
        )

    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"CSV 不存在: {CSV_PATH}"
        )

    # --------------------------------
    # 1. 加载 CSV
    # --------------------------------

    streams = load_streams(
        CSV_PATH
    )

    if args.limit is not None:
        streams = streams[
            : args.limit
        ]

    print()
    print(
        f"准备处理 {len(streams)} 个 Stream"
    )

    # --------------------------------
    # 2. 建立目录索引
    # --------------------------------

    print()
    print("正在建立录播目录索引...")

    directory_index = build_directory_index(
        ARCHIVE_ROOT
    )

    print(
        f"目录索引完成，共 "
        f"{len(directory_index)} "
        f"个不同目录名"
    )

    # --------------------------------
    # 3. 初始化数据库
    # --------------------------------

    connection = connect_db(
        DB_PATH
    )

    init_db(
        connection
    )

    results: list[dict] = []

    try:
        # --------------------------------
        # 4. 一个 Stream 一个事务
        # --------------------------------

        total = len(streams)

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
                directory_index=directory_index,
            )

            results.append(
                result
            )

            if result["status"] == "imported":
                print(
                    "  imported | "
                    f"parts={result['parts']} | "
                    f"danmaku={result['danmaku']}"
                )

            elif result["status"] == "metadata_only":
                print(
                    "  metadata_only | "
                    "未解析到唯一录播目录"
                )

            else:
                print(
                    "  FAILED |",
                    result["error"],
                )

    finally:
        connection.close()

    # --------------------------------
    # 5. 写报告
    # --------------------------------

    write_report(
        results
    )

    print_summary(
        results
    )


if __name__ == "__main__":
    main()