import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


VIEW_API = (
    "https://api.bilibili.com/"
    "x/web-interface/view"
)

NAV_API = (
    "https://api.bilibili.com/"
    "x/web-interface/nav"
)

DANMAKU_SEG_API = (
    "https://api.bilibili.com/"
    "x/v2/dm/web/seg.so"
)

SEGMENT_SECONDS = 360


class BilibiliApiError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BilibiliPart:
    page_index: int

    cid: int

    title: str

    duration_seconds: int


@dataclass(frozen=True, slots=True)
class BilibiliVideoInfo:
    aid: int

    bvid: str

    title: str

    owner: str

    pubdate: int

    parts: list[BilibiliPart]

    video_url: str


@dataclass(frozen=True, slots=True)
class BilibiliDanmakuItem:
    dmid: int

    timestamp_ms: int

    text: str

    weight: int


class BilibiliClient:
    """
    Bilibili 网络访问层。

    sessdata=None：
        Guest Mode。

    sessdata!=None：
        Authenticated Mode。
    """

    def __init__(
        self,
        *,
        sessdata: str | None = None,
        timeout: float = 20.0,
        segment_delay: float = 0.1,
        urlopen: Callable[..., Any] | None = None,
    ) -> None:
        self.sessdata = (
            sessdata.strip()
            if sessdata
            else None
        )

        self.timeout = timeout
        self.segment_delay = (
            segment_delay
        )

        self._urlopen = (
            urlopen
            if urlopen is not None
            else urllib.request.urlopen
        )

    @property
    def authenticated(self) -> bool:
        return bool(
            self.sessdata
        )

    def _build_request(
        self,
        url: str,
        *,
        referer: str | None = None,
    ) -> urllib.request.Request:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; "
                "Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/152.0.0.0 "
                "Safari/537.36"
            ),
            "Accept": "*/*",
        }

        if referer:
            headers["Referer"] = referer

        if self.sessdata:
            headers[
                "Cookie"
            ] = (
                f"SESSDATA="
                f"{self.sessdata}"
            )

        return urllib.request.Request(
            url=url,
            headers=headers,
        )

    def _request_bytes(
        self,
        url: str,
        *,
        referer: str | None = None,
    ) -> bytes:
        request = self._build_request(
            url,
            referer=referer,
        )

        try:
            with self._urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                return response.read()

        except urllib.error.HTTPError as exc:
            raise BilibiliApiError(
                "Bilibili request failed: "
                f"HTTP {exc.code}, "
                f"url={url}"
            ) from exc

        except urllib.error.URLError as exc:
            raise BilibiliApiError(
                "Bilibili request failed: "
                f"{exc.reason}, "
                f"url={url}"
            ) from exc

    def _request_json(
        self,
        url: str,
        *,
        referer: str | None = None,
    ) -> dict:
        body = self._request_bytes(
            url,
            referer=referer,
        )

        try:
            return json.loads(
                body.decode("utf-8")
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise BilibiliApiError(
                "Bilibili returned "
                "invalid JSON"
            ) from exc

    def is_authenticated(self) -> bool:
        """
        验证当前 SESSDATA 是否仍然有效。
        """

        if not self.sessdata:
            return False

        data = self._request_json(
            NAV_API,
            referer=(
                "https://www.bilibili.com/"
            ),
        )

        if data.get("code") != 0:
            return False

        return bool(
            data.get(
                "data",
                {},
            ).get(
                "isLogin",
                False,
            )
        )

    def get_video_info(
        self,
        bvid: str,
    ) -> BilibiliVideoInfo:
        bvid = bvid.strip()

        if not bvid:
            raise ValueError(
                "bvid cannot be empty"
            )

        query = (
            urllib.parse.urlencode(
                {
                    "bvid": bvid,
                }
            )
        )

        url = (
            f"{VIEW_API}?{query}"
        )

        data = self._request_json(
            url,
            referer=(
                "https://www.bilibili.com/"
                f"video/{bvid}"
            ),
        )

        if data.get("code") != 0:
            raise BilibiliApiError(
                "Bilibili video API failed: "
                f"code={data.get('code')}, "
                f"message="
                f"{data.get('message')}"
            )

        payload = data["data"]

        parts: list[
            BilibiliPart
        ] = []

        for page in payload.get(
            "pages",
            [],
        ):
            parts.append(
                BilibiliPart(
                    page_index=(
                        int(
                            page["page"]
                        )
                        - 1
                    ),
                    cid=int(
                        page["cid"]
                    ),
                    title=str(
                        page.get(
                            "part",
                            "",
                        )
                    ),
                    duration_seconds=int(
                        page.get(
                            "duration",
                            0,
                        )
                    ),
                )
            )

        return BilibiliVideoInfo(
            aid=int(
                payload["aid"]
            ),
            bvid=str(
                payload["bvid"]
            ),
            title=str(
                payload.get(
                    "title",
                    "",
                )
            ),
            owner=str(
                payload.get(
                    "owner",
                    {},
                ).get(
                    "name",
                    "",
                )
            ),
            pubdate=int(
                payload.get(
                    "pubdate",
                    0,
                )
            ),
            parts=parts,
            video_url=(
                "https://www.bilibili.com/"
                f"video/{payload['bvid']}"
            ),
        )

    def get_part_danmaku(
        self,
        *,
        video: BilibiliVideoInfo,
        part: BilibiliPart,
    ) -> list[BilibiliDanmakuItem]:
        """
        读取一个 Part 的 segmented danmaku。

        登录与否使用完全相同的接口。
        区别只在请求中是否携带 SESSDATA。
        """

        segment_count = max(
            1,
            math.ceil(
                part.duration_seconds
                / SEGMENT_SECONDS
            ),
        )

        results: list[
            BilibiliDanmakuItem
        ] = []

        for segment_index in range(
            1,
            segment_count + 1,
        ):
            body = (
                self._fetch_segment(
                    video=video,
                    part=part,
                    segment_index=(
                        segment_index
                    ),
                )
            )

            results.extend(
                parse_danmaku_segment(
                    body
                )
            )

            if (
                self.segment_delay > 0
                and segment_index
                < segment_count
            ):
                time.sleep(
                    self.segment_delay
                )

        return deduplicate_danmaku(
            results
        )

    def _fetch_segment(
        self,
        *,
        video: BilibiliVideoInfo,
        part: BilibiliPart,
        segment_index: int,
    ) -> bytes:
        query = (
            urllib.parse.urlencode(
                {
                    "type": 1,
                    "oid": part.cid,
                    "pid": video.aid,
                    "segment_index": (
                        segment_index
                    ),
                }
            )
        )

        url = (
            f"{DANMAKU_SEG_API}"
            f"?{query}"
        )

        body = self._request_bytes(
            url,
            referer=video.video_url,
        )

        stripped = body.lstrip()

        if stripped.startswith(
            b"{"
        ):
            try:
                error_payload = (
                    json.loads(
                        body.decode(
                            "utf-8"
                        )
                    )
                )
            except Exception:
                error_payload = (
                    body[:200]
                )

            raise BilibiliApiError(
                "Bilibili returned JSON "
                "instead of protobuf: "
                f"{error_payload}"
            )

        if stripped.startswith(
            b"<"
        ):
            raise BilibiliApiError(
                "Bilibili returned "
                "HTML/XML instead of "
                "protobuf"
            )

        return body


def _read_varint(
    data: bytes,
    offset: int,
) -> tuple[int, int]:
    value = 0
    shift = 0

    while True:
        if offset >= len(data):
            raise ValueError(
                "Unexpected end of "
                "protobuf varint"
            )

        byte = data[offset]
        offset += 1

        value |= (
            byte & 0x7F
        ) << shift

        if not (
            byte & 0x80
        ):
            return (
                value,
                offset,
            )

        shift += 7

        if shift >= 70:
            raise ValueError(
                "Invalid protobuf varint"
            )


def _read_wire_value(
    data: bytes,
    offset: int,
    wire_type: int,
) -> tuple[Any, int]:
    if wire_type == 0:
        return _read_varint(
            data,
            offset,
        )

    if wire_type == 1:
        end = offset + 8

        if end > len(data):
            raise ValueError(
                "Invalid protobuf fixed64"
            )

        return (
            data[offset:end],
            end,
        )

    if wire_type == 2:
        length, offset = (
            _read_varint(
                data,
                offset,
            )
        )

        end = offset + length

        if end > len(data):
            raise ValueError(
                "Invalid protobuf "
                "length-delimited field"
            )

        return (
            data[offset:end],
            end,
        )

    if wire_type == 5:
        end = offset + 4

        if end > len(data):
            raise ValueError(
                "Invalid protobuf fixed32"
            )

        return (
            data[offset:end],
            end,
        )

    raise ValueError(
        "Unsupported protobuf "
        f"wire type: {wire_type}"
    )


def _parse_danmaku_elem(
    data: bytes,
) -> BilibiliDanmakuItem:
    offset = 0

    dmid = 0
    progress = 0
    content = ""
    weight = 0

    while offset < len(data):
        key, offset = _read_varint(
            data,
            offset,
        )

        field_number = (
            key >> 3
        )

        wire_type = (
            key & 0x07
        )

        value, offset = (
            _read_wire_value(
                data,
                offset,
                wire_type,
            )
        )

        if (
            field_number == 1
            and wire_type == 0
        ):
            dmid = int(value)

        elif (
            field_number == 2
            and wire_type == 0
        ):
            progress = int(
                value
            )

        elif (
            field_number == 7
            and wire_type == 2
        ):
            content = value.decode(
                "utf-8",
                errors="replace",
            )

        elif (
            field_number == 9
            and wire_type == 0
        ):
            weight = int(
                value
            )

    return BilibiliDanmakuItem(
        dmid=dmid,
        timestamp_ms=progress,
        text=content.strip(),
        weight=weight,
    )


def parse_danmaku_segment(
    data: bytes,
) -> list[BilibiliDanmakuItem]:
    """
    DmSegMobileReply:

    field 1:
        repeated DanmakuElem elems
    """

    offset = 0

    results: list[
        BilibiliDanmakuItem
    ] = []

    while offset < len(data):
        key, offset = _read_varint(
            data,
            offset,
        )

        field_number = (
            key >> 3
        )

        wire_type = (
            key & 0x07
        )

        value, offset = (
            _read_wire_value(
                data,
                offset,
                wire_type,
            )
        )

        if (
            field_number == 1
            and wire_type == 2
        ):
            item = (
                _parse_danmaku_elem(
                    value
                )
            )

            if item.text:
                results.append(
                    item
                )

    return results


def deduplicate_danmaku(
    danmaku: list[
        BilibiliDanmakuItem
    ],
) -> list[BilibiliDanmakuItem]:
    seen: set[tuple] = set()

    results: list[
        BilibiliDanmakuItem
    ] = []

    for item in danmaku:
        if item.dmid:
            key = (
                "id",
                item.dmid,
            )
        else:
            key = (
                "fallback",
                item.timestamp_ms,
                item.text,
            )

        if key in seen:
            continue

        seen.add(key)

        results.append(
            item
        )

    results.sort(
        key=lambda item: (
            item.timestamp_ms,
            item.dmid,
        )
    )

    return results