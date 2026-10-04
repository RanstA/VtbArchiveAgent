import argparse
import urllib.parse

from app.ingestion.bilibili_client import (
    BilibiliClient,
    BilibiliApiError,
)
from app.ingestion.bilibili_session import (
    BilibiliSessionStore,
)

PLAYER_WBI_API = "https://api.bilibili.com/" "x/player/wbi/v2"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=("Probe Bilibili subtitle metadata " "for every part of a video.")
    )

    parser.add_argument(
        "--bvid",
        default="BV1pnhf6QE8Z",
        help="Bilibili BV id",
    )

    args = parser.parse_args()

    bvid = args.bvid.strip()

    if not bvid:
        raise ValueError("bvid cannot be empty")

    store = BilibiliSessionStore()
    session = store.load()

    if session is None:
        raise RuntimeError(
            "No valid Bilibili session found.\n"
            "Please login first with the project's "
            "Bilibili session script."
        )

    client = BilibiliClient(
        sessdata=session.sessdata,
    )

    print()
    print("=" * 72)
    print("Bilibili Subtitle Probe")
    print("=" * 72)

    print("BVID:", bvid)
    print(
        "Authenticated:",
        client.is_authenticated(),
    )

    video = client.get_video_info(bvid)

    print("Title:", video.title)
    print("Parts:", len(video.parts))

    for part in video.parts:
        print()
        print("-" * 72)

        print("Part:", f"p{part.page_index}")
        print("Page:", part.page_index + 1)
        print("CID:", part.cid)
        print("Title:", part.title)
        print("Duration:", part.duration_seconds, "seconds")

        query = urllib.parse.urlencode({"bvid": bvid, "cid": part.cid})

        url = f"{PLAYER_WBI_API}" f"?{query}"

        try:
            data = client._request_json(url, referer=video.video_url)

        except BilibiliApiError as exc:
            print("Request failed:", str(exc))
            continue

        code = data.get("code")
        message = data.get("message", "")

        print("API code:", code)
        print("API message:", message)

        if code != 0:
            print("Subtitle metadata request " "did not succeed.")
            continue

        payload = data.get("data", {})

        subtitle = payload.get("subtitle", {}) or {}

        need_login = subtitle.get(
            "need_login_subtitle",
            payload.get(
                "need_login_subtitle",
            ),
        )

        tracks = subtitle.get("subtitles", []) or []

        print("Need login:", need_login)
        print("Subtitle tracks:", len(tracks))

        if not tracks:
            print("No subtitle tracks returned.")
            continue

        for index, track in enumerate(tracks, start=1):
            print()
            print(f"  Track #{index}")
            print(
                "    id:",
                track.get("id"),
            )
            print(
                "    lan:",
                track.get("lan"),
            )
            print(
                "    lan_doc:",
                track.get("lan_doc"),
            )
            print(
                "    ai_type:",
                track.get("ai_type"),
            )
            print(
                "    ai_status:",
                track.get("ai_status"),
            )
            print(
                "    subtitle_url:",
                track.get("subtitle_url"),
            )

if __name__ == "__main__":
    main()