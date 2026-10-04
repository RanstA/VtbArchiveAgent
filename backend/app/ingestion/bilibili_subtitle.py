from __future__ import annotations

from dataclasses import dataclass
import urllib.parse

from app.ingestion.bilibili_client import (
    BilibiliApiError,
    BilibiliClient,
)

PLAYER_WBI_API = "https://api.bilibili.com/" "x/player/wbi/v2"


@dataclass(
    frozen=True,
    slots=True,
)
class BilibiliSubtitleItem:
    """
    Bilibili 单条字幕。

    start_ms / end_ms 均为当前 Part 内的局部时间。
    """

    start_ms: int
    end_ms: int
    text: str


def _normalize_subtitle_url(
    value: str,
) -> str:
    value = value.strip()

    if value.startswith("//"):
        return "https:" + value

    return value


def get_ai_chinese_subtitles(
    client: BilibiliClient,
    *,
    bvid: str,
    cid: int | str,
) -> list[BilibiliSubtitleItem]:
    """
    获取一个 Bilibili Part 的 AI 中文字幕。

    返回的时间均为 Part-local 毫秒。

    如果当前 Part 没有 ai-zh 字幕轨道，
    返回空列表。
    """

    bvid = bvid.strip()

    if not bvid:
        raise ValueError("bvid cannot be empty")

    cid_text = str(cid).strip()

    if not cid_text:
        raise ValueError("cid cannot be empty")

    referer = "https://www.bilibili.com/" f"video/{bvid}"

    query = urllib.parse.urlencode(
        {
            "bvid": bvid,
            "cid": cid_text,
        }
    )

    metadata_url = f"{PLAYER_WBI_API}" f"?{query}"

    metadata = client._request_json(
        metadata_url,
        referer=referer,
    )

    if metadata.get("code") != 0:
        raise BilibiliApiError(
            "Bilibili subtitle metadata "
            "request failed: "
            f"code={metadata.get('code')}, "
            f"message={metadata.get('message')}"
        )

    subtitle_payload = (
        metadata.get(
            "data",
            {},
        ).get(
            "subtitle",
            {},
        )
        or {}
    )

    tracks = (
        subtitle_payload.get(
            "subtitles",
            [],
        )
        or []
    )

    zh_track = next(
        (track for track in tracks if (track.get("lan") == "ai-zh")),
        None,
    )

    if zh_track is None:
        return []

    raw_subtitle_url = str(
        zh_track.get(
            "subtitle_url",
            "",
        )
    )

    subtitle_url = _normalize_subtitle_url(raw_subtitle_url)

    if not subtitle_url:
        raise BilibiliApiError("Bilibili ai-zh subtitle " "track has no subtitle_url")

    body_payload = client._request_json(
        subtitle_url,
        referer=referer,
    )

    raw_body = (
        body_payload.get(
            "body",
            [],
        )
        or []
    )

    results: list[BilibiliSubtitleItem] = []

    for index, item in enumerate(raw_body):
        text = str(
            item.get(
                "content",
                "",
            )
        ).strip()

        if not text:
            continue

        try:
            start_seconds = float(item["from"])
            end_seconds = float(item["to"])
        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise BilibiliApiError(
                "Invalid subtitle timing " f"at row {index}"
            ) from exc

        start_ms = round(start_seconds * 1000)

        end_ms = round(end_seconds * 1000)

        if start_ms < 0:
            raise BilibiliApiError(
                "Subtitle start time " f"must be >= 0 at row {index}"
            )

        if end_ms <= start_ms:
            raise BilibiliApiError(
                "Subtitle end time must "
                "be greater than start "
                f"time at row {index}"
            )

        results.append(
            BilibiliSubtitleItem(
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
            )
        )

    return results
