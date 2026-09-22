import argparse
import json
from dataclasses import (
    asdict,
)
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

from app.ingestion.bilibili_discovery import (
    BilibiliDiscoveryClient,
)
from app.ingestion.bilibili_session import (
    BilibiliSessionStore,
)


CHINA_TZ = timezone(
    timedelta(
        hours=8
    )
)


def years_ago(
    now: datetime,
    years: int,
) -> datetime:
    try:
        return now.replace(
            year=(
                now.year
                - years
            )
        )

    except ValueError:
        # 例如 2 月 29 日。
        return now.replace(
            year=(
                now.year
                - years
            ),
            day=28,
        )


def build_client(
    auth_mode: str,
) -> tuple[
    BilibiliDiscoveryClient,
    bool,
]:
    if auth_mode == "guest":
        return (
            BilibiliDiscoveryClient(),
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
            raise RuntimeError(
                "No cached Bilibili "
                "session.\n"
                "Run:\n"
                "python -m "
                "scripts.bilibili_session "
                "login"
            )

        return (
            BilibiliDiscoveryClient(),
            False,
        )

    client = (
        BilibiliDiscoveryClient(
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
        raise RuntimeError(
            "Cached Bilibili "
            "session is no longer valid."
        )

    return (
        BilibiliDiscoveryClient(),
        False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Discover recent Bilibili "
            "live replay uploads for "
            "a known VTuber."
        )
    )

    parser.add_argument(
        "--vtuber-id",
        required=True,
        help=(
            "内部稳定 VTuber ID，"
            "例如 aza"
        ),
    )

    parser.add_argument(
        "--vtuber-name",
        required=True,
        help=(
            "显示名称，例如 阿萨Aza"
        ),
    )

    parser.add_argument(
        "--seed-bvid",
        required=True,
        help=(
            "一条确认属于该 VTuber "
            "本人账号的 BVID"
        ),
    )

    parser.add_argument(
        "--years",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--keyword",
        default="直播回放",
    )

    parser.add_argument(
        "--page-size",
        type=int,
        default=30,
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help=(
            "调试时最多读取多少页。"
            "默认不限。"
        ),
    )

    parser.add_argument(
        "--auth-mode",
        choices=[
            "auto",
            "guest",
            "authenticated",
        ],
        default="auto",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )

    args = parser.parse_args()

    if args.years < 1:
        parser.error(
            "--years must be >= 1"
        )

    if not (
        1
        <= args.page_size
        <= 50
    ):
        parser.error(
            "--page-size must be "
            "between 1 and 50"
        )

    if (
        args.max_pages is not None
        and args.max_pages < 1
    ):
        parser.error(
            "--max-pages must be >= 1"
        )

    vtuber_id = (
        args.vtuber_id
        .strip()
    )

    vtuber_name = (
        args.vtuber_name
        .strip()
    )

    seed_bvid = (
        args.seed_bvid
        .strip()
    )

    keyword = (
        args.keyword
        .strip()
    )

    if not vtuber_id:
        parser.error(
            "--vtuber-id "
            "cannot be empty"
        )

    if not vtuber_name:
        parser.error(
            "--vtuber-name "
            "cannot be empty"
        )

    if not seed_bvid:
        parser.error(
            "--seed-bvid "
            "cannot be empty"
        )

    if not keyword:
        parser.error(
            "--keyword "
            "cannot be empty"
        )

    output_path = (
        args.output
        if args.output
        is not None
        else (
            Path(".local")
            / "discovery"
            / (
                f"{vtuber_id}"
                "_replays.json"
            )
        )
    )

    now = datetime.now(
        CHINA_TZ
    )

    cutoff = years_ago(
        now,
        args.years,
    )

    client, authenticated = (
        build_client(
            args.auth_mode
        )
    )

    print()
    print("=" * 70)
    print(
        "Bilibili Replay Inventory"
    )
    print("=" * 70)

    print(
        "VTuber:",
        f"{vtuber_name} "
        f"({vtuber_id})",
    )

    print(
        "Seed BVID:",
        seed_bvid,
    )

    print(
        "Keyword:",
        keyword,
    )

    print(
        "Cutoff:",
        cutoff.isoformat(),
    )

    print(
        "Authenticated:",
        authenticated,
    )

    print()
    print(
        "Resolving uploader..."
    )

    uploader = (
        client
        .resolve_uploader_from_bvid(
            seed_bvid
        )
    )

    print(
        "Uploader:",
        uploader.display_name,
    )

    print(
        "MID:",
        uploader.mid,
    )

    print()
    print(
        "Scanning uploads..."
    )

    replays = (
        client.list_recent_replays(
            mid=uploader.mid,
            since_timestamp=int(
                cutoff.timestamp()
            ),
            keyword=keyword,
            page_size=(
                args.page_size
            ),
            max_pages=(
                args.max_pages
            ),
        )
    )

    candidate_payload = []

    for replay in replays:
        published_at = (
            datetime.fromtimestamp(
                replay.created,
                tz=CHINA_TZ,
            )
        )

        candidate_payload.append(
            {
                **asdict(
                    replay
                ),
                "published_at": (
                    published_at
                    .isoformat()
                ),
                "video_url": (
                    "https://www.bilibili.com/"
                    f"video/{replay.bvid}"
                ),
            }
        )

    payload = {
        "generated_at": (
            now.isoformat()
        ),
        "vtuber": {
            "id": vtuber_id,
            "display_name": (
                vtuber_name
            ),
        },
        "source": {
            "type": "bilibili",
            "external_id": str(
                uploader.mid
            ),
            "display_name": (
                uploader.display_name
            ),
            "seed_bvid": (
                seed_bvid
            ),
        },
        "query": {
            "years": (
                args.years
            ),
            "cutoff": (
                cutoff.isoformat()
            ),
            "keyword": (
                keyword
            ),
        },
        "authenticated": (
            authenticated
        ),
        "summary": {
            "replay_count": (
                len(replays)
            ),
        },
        "replays": (
            candidate_payload
        ),
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 70)

    print(
        "Replay count:",
        len(replays),
    )

    print()

    for replay in replays[
        :10
    ]:
        published_at = (
            datetime.fromtimestamp(
                replay.created,
                tz=CHINA_TZ,
            )
        )

        print(
            published_at.strftime(
                "%Y-%m-%d"
            ),
            replay.bvid,
            replay.title,
        )

    if len(replays) > 10:
        print(
            f"... and "
            f"{len(replays) - 10} "
            f"more"
        )

    print()

    print(
        "Inventory:",
        output_path.resolve(),
    )

    print("=" * 70)


if __name__ == "__main__":
    main()