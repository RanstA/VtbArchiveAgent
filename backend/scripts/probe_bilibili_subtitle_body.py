import argparse

from app.ingestion.bilibili_client import (
    BilibiliApiError,
    BilibiliClient,
)
from app.ingestion.bilibili_session import (
    BilibiliSessionStore,
)


PLAYER_WBI_API = (
    "https://api.bilibili.com/"
    "x/player/wbi/v2"
)


def normalize_subtitle_url(
    value: str,
) -> str:
    value = value.strip()

    if value.startswith("//"):
        return "https:" + value

    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Probe one Bilibili AI Chinese "
            "subtitle body."
        )
    )

    parser.add_argument(
        "--bvid",
        default="BV1pnhf6QE8Z",
        help="Bilibili BV id",
    )

    parser.add_argument(
        "--part",
        type=int,
        default=0,
        help="Zero-based part index, default: 0",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="How many subtitle rows to print",
    )

    args = parser.parse_args()

    if args.part < 0:
        raise ValueError(
            "--part must be >= 0"
        )

    if args.limit < 1:
        raise ValueError(
            "--limit must be >= 1"
        )

    store = BilibiliSessionStore()
    session = store.load()

    if session is None:
        raise RuntimeError(
            "No valid Bilibili session found."
        )

    client = BilibiliClient(
        sessdata=session.sessdata,
    )

    video = client.get_video_info(
        args.bvid
    )

    if args.part >= len(video.parts):
        raise ValueError(
            f"--part out of range: "
            f"{args.part}; "
            f"video has {len(video.parts)} parts"
        )

    part = video.parts[
        args.part
    ]

    import urllib.parse

    query = urllib.parse.urlencode(
        {
            "bvid": args.bvid,
            "cid": part.cid,
        }
    )

    metadata_url = (
        f"{PLAYER_WBI_API}"
        f"?{query}"
    )

    metadata = client._request_json(
        metadata_url,
        referer=video.video_url,
    )

    if metadata.get("code") != 0:
        raise BilibiliApiError(
            "Subtitle metadata request failed: "
            f"code={metadata.get('code')}, "
            f"message={metadata.get('message')}"
        )

    subtitle = (
        metadata
        .get("data", {})
        .get("subtitle", {})
        or {}
    )

    tracks = (
        subtitle.get(
            "subtitles",
            [],
        )
        or []
    )

    zh_track = next(
        (
            track
            for track in tracks
            if track.get("lan")
            == "ai-zh"
        ),
        None,
    )

    if zh_track is None:
        raise RuntimeError(
            "No ai-zh subtitle track found"
        )

    raw_url = str(
        zh_track.get(
            "subtitle_url",
            "",
        )
    )

    subtitle_url = (
        normalize_subtitle_url(
            raw_url
        )
    )

    if not subtitle_url:
        raise RuntimeError(
            "ai-zh track has no subtitle_url"
        )

    body_json = client._request_json(
        subtitle_url,
        referer=video.video_url,
    )

    body = body_json.get(
        "body",
        [],
    ) or []

    print()
    print("=" * 72)
    print("Bilibili Subtitle Body Probe")
    print("=" * 72)

    print("BVID:", args.bvid)
    print("Title:", video.title)
    print(
        "Part:",
        f"p{part.page_index}",
    )
    print("CID:", part.cid)
    print(
        "Duration:",
        part.duration_seconds,
        "seconds",
    )
    print(
        "Track:",
        zh_track.get("lan"),
        zh_track.get("lan_doc"),
    )
    print(
        "Subtitle rows:",
        len(body),
    )

    if body:
        first_from = body[0].get(
            "from"
        )
        last_to = body[-1].get(
            "to"
        )

        print(
            "First timestamp:",
            first_from,
        )
        print(
            "Last timestamp:",
            last_to,
        )

        if (
            isinstance(
                last_to,
                (int, float),
            )
            and last_to
            > part.duration_seconds + 10
        ):
            print(
                "WARNING: subtitle end time "
                "exceeds part duration by >10s"
            )

    print()
    print(
        f"First {min(args.limit, len(body))} rows:"
    )

    for index, item in enumerate(
        body[:args.limit],
        start=1,
    ):
        start = item.get(
            "from"
        )
        end = item.get(
            "to"
        )
        text = str(
            item.get(
                "content",
                "",
            )
        ).strip()

        print(
            f"{index:>3}. "
            f"{start} -> {end} | "
            f"{text}"
        )

    print()
    print("=" * 72)
    print("Probe finished")
    print("=" * 72)


if __name__ == "__main__":
    main()
