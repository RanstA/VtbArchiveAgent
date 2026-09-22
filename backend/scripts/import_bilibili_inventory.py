from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from typing import Any

from app.domain.vtuber import (
    Vtuber,
    VtuberSource,
)
from app.ingestion.bilibili_client import (
    BilibiliClient,
)
from app.ingestion.bilibili_session import (
    BilibiliSessionStore,
)
from app.ingestion.bilibili_source import (
    BilibiliAuthenticationError,
    BilibiliSource,
)
from app.ingestion.persist import (
    persist_archive_bundle,
)
from app.repository.database import (
    connect_db,
    init_db,
)


@dataclass(
    frozen=True,
    slots=True,
)
class InventoryReplay:
    bvid: str
    title: str
    published_at: str | None


@dataclass(
    frozen=True,
    slots=True,
)
class Inventory:
    vtuber_id: str
    vtuber_name: str

    source_type: str
    source_external_id: str
    source_display_name: str

    replays: list[InventoryReplay]


def require_non_empty_string(
    value: Any,
    *,
    field_name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise ValueError(
            f"{field_name} must be a string"
        )

    result = value.strip()

    if not result:
        raise ValueError(
            f"{field_name} cannot be empty"
        )

    return result


def load_inventory(
    path: Path,
) -> Inventory:
    if not path.exists():
        raise FileNotFoundError(
            f"Inventory not found: {path}"
        )

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            "Inventory root must be an object"
        )

    vtuber_payload = payload.get(
        "vtuber"
    )

    if not isinstance(
        vtuber_payload,
        dict,
    ):
        raise ValueError(
            "Inventory vtuber must be an object"
        )

    source_payload = payload.get(
        "source"
    )

    if not isinstance(
        source_payload,
        dict,
    ):
        raise ValueError(
            "Inventory source must be an object"
        )

    source_type = (
        require_non_empty_string(
            source_payload.get(
                "type"
            ),
            field_name=(
                "source.type"
            ),
        )
    )

    if source_type != "bilibili":
        raise ValueError(
            "Only Bilibili inventory "
            "is supported"
        )

    raw_replays = payload.get(
        "replays"
    )

    if not isinstance(
        raw_replays,
        list,
    ):
        raise ValueError(
            "Inventory replays must be a list"
        )

    replays: list[
        InventoryReplay
    ] = []

    seen_bvids: set[str] = set()

    for index, raw_replay in enumerate(
        raw_replays
    ):
        if not isinstance(
            raw_replay,
            dict,
        ):
            raise ValueError(
                "Inventory replay "
                f"#{index} must be an object"
            )

        bvid = require_non_empty_string(
            raw_replay.get(
                "bvid"
            ),
            field_name=(
                f"replays[{index}].bvid"
            ),
        )

        if bvid in seen_bvids:
            continue

        seen_bvids.add(
            bvid
        )

        title = str(
            raw_replay.get(
                "title",
                "",
            )
        ).strip()

        published_at_value = (
            raw_replay.get(
                "published_at"
            )
        )

        published_at = (
            str(
                published_at_value
            ).strip()
            if published_at_value
            is not None
            else None
        )

        replays.append(
            InventoryReplay(
                bvid=bvid,
                title=title,
                published_at=(
                    published_at
                ),
            )
        )

    return Inventory(
        vtuber_id=(
            require_non_empty_string(
                vtuber_payload.get(
                    "id"
                ),
                field_name=(
                    "vtuber.id"
                ),
            )
        ),
        vtuber_name=(
            require_non_empty_string(
                vtuber_payload.get(
                    "display_name"
                ),
                field_name=(
                    "vtuber.display_name"
                ),
            )
        ),
        source_type=source_type,
        source_external_id=(
            require_non_empty_string(
                source_payload.get(
                    "external_id"
                ),
                field_name=(
                    "source.external_id"
                ),
            )
        ),
        source_display_name=(
            require_non_empty_string(
                source_payload.get(
                    "display_name"
                ),
                field_name=(
                    "source.display_name"
                ),
            )
        ),
        replays=replays,
    )


def find_stream_id_by_bvid(
    connection,
    bvid: str,
) -> str | None:
    row = connection.execute(
        """
        SELECT stream_id
        FROM stream_bv_ids
        WHERE bv_id = ?
        LIMIT 1
        """,
        (bvid,),
    ).fetchone()

    if row is None:
        return None

    return str(
        row[0]
    )


def build_bilibili_client(
    auth_mode: str,
) -> tuple[
    BilibiliClient,
    bool,
]:
    """
    整个批量任务只验证一次登录态。

    后续所有 BilibiliSource
    共享同一个 client，
    避免每个 BVID 都重复请求 nav。
    """

    if auth_mode == "guest":
        return (
            BilibiliClient(),
            False,
        )

    store = (
        BilibiliSessionStore()
    )

    session = store.load()

    if session is None:
        if (
            auth_mode
            == "authenticated"
        ):
            raise (
                BilibiliAuthenticationError(
                    "No valid Bilibili "
                    "session found.\n"
                    "Run:\n"
                    "python -m "
                    "scripts.bilibili_session "
                    "login"
                )
            )

        return (
            BilibiliClient(),
            False,
        )

    client = (
        BilibiliClient(
            sessdata=(
                session.sessdata
            )
        )
    )

    if client.is_authenticated():
        return (
            client,
            True,
        )

    store.clear()

    if (
        auth_mode
        == "authenticated"
    ):
        raise (
            BilibiliAuthenticationError(
                "Cached Bilibili session "
                "is no longer valid"
            )
        )

    return (
        BilibiliClient(),
        False,
    )


def enrich_bilibili_source_identity(
    bundle,
    *,
    inventory: Inventory,
) -> None:
    """
    Discovery 阶段已经拿到了稳定的 Bilibili MID。

    当前 BilibiliSource 单 BVID ingestion
    还不会自动把 owner.mid 放进 VtuberSource，
    因此在批量导入边界补上它。

    这样数据库最终保存的是：

        vtuber_id = aza
        source = bilibili
        external_id = 480680646
        display_name = 阿萨Aza
    """

    owner = str(
        bundle.source_metadata.get(
            "owner",
            inventory.source_display_name,
        )
    ).strip()

    if not owner:
        owner = (
            inventory.source_display_name
        )

    bundle.vtuber_sources = [
        VtuberSource(
            vtuber_id=(
                inventory.vtuber_id
            ),
            source="bilibili",
            external_id=(
                inventory
                .source_external_id
            ),
            display_name=owner,
        )
    ]


def write_report(
    path: Path,
    *,
    inventory: Inventory,
    database_path: Path,
    authenticated: bool,
    imported: list[dict],
    skipped: list[dict],
    failed: list[dict],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "generated_at": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "vtuber": {
            "id": (
                inventory.vtuber_id
            ),
            "display_name": (
                inventory.vtuber_name
            ),
        },
        "source": {
            "type": (
                inventory.source_type
            ),
            "external_id": (
                inventory
                .source_external_id
            ),
            "display_name": (
                inventory
                .source_display_name
            ),
        },
        "database": str(
            database_path.resolve()
        ),
        "authenticated": (
            authenticated
        ),
        "summary": {
            "imported": len(
                imported
            ),
            "skipped": len(
                skipped
            ),
            "failed": len(
                failed
            ),
        },
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
    }

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Import cached Bilibili "
            "replay inventory into "
            "VtbArchiveAgent SQLite."
        )
    )

    parser.add_argument(
        "--inventory",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=Path(
            "vtuber_archive.db"
        ),
    )

    parser.add_argument(
        "--auth-mode",
        choices=[
            "auto",
            "guest",
            "authenticated",
        ],
        default="authenticated",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "最多处理 inventory "
            "中的前 N 条。"
        ),
    )

    parser.add_argument(
        "--video-delay",
        type=float,
        default=1.0,
        help=(
            "相邻两个 BVID 之间 "
            "等待的秒数。"
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "即使 BVID 已存在于 DB，"
            "也重新抓取并覆盖其 "
            "Parts / Danmaku。"
        ),
    )

    parser.add_argument(
        "--report",
        type=Path,
        default=None,
    )

    args = parser.parse_args()

    if (
        args.limit is not None
        and args.limit < 1
    ):
        parser.error(
            "--limit must be >= 1"
        )

    if args.video_delay < 0:
        parser.error(
            "--video-delay must be >= 0"
        )

    inventory = (
        load_inventory(
            args.inventory
        )
    )

    candidates = (
        inventory.replays
    )

    if args.limit is not None:
        candidates = (
            candidates[
                : args.limit
            ]
        )

    report_path = (
        args.report
        if args.report
        is not None
        else (
            Path(".local")
            / "import"
            / (
                f"{inventory.vtuber_id}"
                "_last_import.json"
            )
        )
    )

    vtuber = Vtuber(
        id=(
            inventory.vtuber_id
        ),
        display_name=(
            inventory.vtuber_name
        ),
    )

    print()
    print("=" * 72)
    print(
        "Bilibili Inventory Import"
    )
    print("=" * 72)

    print(
        "VTuber:",
        f"{vtuber.display_name} "
        f"({vtuber.id})",
    )

    print(
        "Bilibili MID:",
        inventory.source_external_id,
    )

    print(
        "Inventory:",
        args.inventory.resolve(),
    )

    print(
        "Database:",
        args.db.resolve(),
    )

    print(
        "Candidates:",
        len(candidates),
    )

    print(
        "Force:",
        args.force,
    )

    print()
    print(
        "Checking Bilibili session..."
    )

    client, authenticated = (
        build_bilibili_client(
            args.auth_mode
        )
    )

    print(
        "Authenticated:",
        authenticated,
    )

    connection = connect_db(
        args.db
    )

    imported: list[
        dict
    ] = []

    skipped: list[
        dict
    ] = []

    failed: list[
        dict
    ] = []

    try:
        init_db(
            connection
        )

        for index, replay in enumerate(
            candidates,
            start=1,
        ):
            print()
            print("-" * 72)

            print(
                f"[{index}/{len(candidates)}]",
                replay.bvid,
            )

            if replay.title:
                print(
                    "Title:",
                    replay.title,
                )

            existing_stream_id = (
                find_stream_id_by_bvid(
                    connection,
                    replay.bvid,
                )
            )

            if (
                existing_stream_id
                is not None
                and not args.force
            ):
                print(
                    "SKIP:",
                    "already imported",
                )

                print(
                    "Stream ID:",
                    existing_stream_id,
                )

                skipped.append(
                    {
                        "bvid": (
                            replay.bvid
                        ),
                        "title": (
                            replay.title
                        ),
                        "reason": (
                            "already_imported"
                        ),
                        "stream_id": (
                            existing_stream_id
                        ),
                    }
                )

                continue

            try:
                print(
                    "Fetching video / "
                    "parts / danmaku..."
                )

                source = (
                    BilibiliSource(
                        bvid=(
                            replay.bvid
                        ),
                        vtuber=vtuber,

                        # provided client 已经在任务开始时
                        # 完成登录态判断，
                        # 因此这里不会每场重新验证 nav。
                        client=client,

                        auth_mode=(
                            args.auth_mode
                        ),
                    )
                )

                bundle = (
                    source.load()
                )

                if (
                    replay.bvid
                    not in
                    bundle.stream.bv_ids
                ):
                    raise RuntimeError(
                        "Loaded bundle does not "
                        "contain requested BVID: "
                        f"{replay.bvid}"
                    )

                enrich_bilibili_source_identity(
                    bundle,
                    inventory=inventory,
                )

                print(
                    "Live time:",
                    bundle.stream.live_time,
                )

                print(
                    "Parts:",
                    len(
                        bundle.parts
                    ),
                )

                print(
                    "Danmaku:",
                    len(
                        bundle.danmaku
                    ),
                )

                print(
                    "Writing SQLite..."
                )

                persist_archive_bundle(
                    connection=connection,
                    bundle=bundle,
                )

                imported.append(
                    {
                        "bvid": (
                            replay.bvid
                        ),
                        "title": (
                            bundle.stream.title
                        ),
                        "stream_id": (
                            bundle.stream.id
                        ),
                        "live_time": (
                            bundle.stream
                            .live_time
                            .isoformat()
                        ),
                        "parts": len(
                            bundle.parts
                        ),
                        "danmaku": len(
                            bundle.danmaku
                        ),
                    }
                )

                print(
                    "OK:",
                    bundle.stream.id,
                )

            except Exception as exc:
                failed.append(
                    {
                        "bvid": (
                            replay.bvid
                        ),
                        "title": (
                            replay.title
                        ),
                        "error_type": (
                            type(
                                exc
                            ).__name__
                        ),
                        "error": str(
                            exc
                        ),
                    }
                )

                print(
                    "FAILED:",
                    type(
                        exc
                    ).__name__,
                    str(
                        exc
                    ),
                )

            if (
                index
                < len(candidates)
                and args.video_delay > 0
            ):
                time.sleep(
                    args.video_delay
                )

    finally:
        connection.close()

        write_report(
            report_path,
            inventory=inventory,
            database_path=args.db,
            authenticated=authenticated,
            imported=imported,
            skipped=skipped,
            failed=failed,
        )

    print()
    print("=" * 72)
    print(
        "Import Summary"
    )
    print("=" * 72)

    print(
        "Imported:",
        len(imported),
    )

    print(
        "Skipped:",
        len(skipped),
    )

    print(
        "Failed:",
        len(failed),
    )

    print()

    print(
        "Report:",
        report_path.resolve(),
    )

    print("=" * 72)

    if failed:
        print()
        print(
            "Failed BVIDs:"
        )

        for item in failed:
            print(
                " ",
                item["bvid"],
                "-",
                item["error"],
            )


if __name__ == "__main__":
    main()