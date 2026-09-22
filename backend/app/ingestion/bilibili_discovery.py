from __future__ import annotations

import time
import urllib.parse
from dataclasses import dataclass

from app.ingestion.bilibili_client import (
    BilibiliApiError,
    BilibiliClient,
    VIEW_API,
)


REPLAY_LIST_API = (
    "https://api.bilibili.com/"
    "x/series/recArchivesByKeywords"
)


@dataclass(
    frozen=True,
    slots=True,
)
class BilibiliUploaderIdentity:
    mid: int
    display_name: str


@dataclass(
    frozen=True,
    slots=True,
)
class BilibiliUpload:
    aid: int
    bvid: str

    title: str
    created: int

    length: str

    author: str


@dataclass(
    frozen=True,
    slots=True,
)
class BilibiliUploadPage:
    items: list[BilibiliUpload]

    total: int

    page_number: int
    page_size: int


def is_replay_title(
    title: str,
    *,
    keyword: str = "直播回放",
) -> bool:
    """
    Closed Alpha 阶段使用保守规则。

    当前已验证 Aza 历史录播存在：

        【直播回放】...
        2023年12月20日20点场

    因此暂时只收标题中明确包含
    “直播回放”的投稿。

    等 inventory 出来后再人工检查
    是否存在其他历史命名格式。
    """

    normalized_title = (
        title.strip()
    )

    normalized_keyword = (
        keyword.strip()
    )

    if not normalized_title:
        return False

    if not normalized_keyword:
        return False

    return (
        normalized_keyword
        in normalized_title
    )


class BilibiliDiscoveryClient(
    BilibiliClient
):
    """
    Bilibili 投稿发现层。

    BilibiliClient:
        已知 BVID
        -> video / parts / danmaku

    BilibiliDiscoveryClient:
        已知一条主播本人 BVID
        -> owner MID
        -> replay inventory
    """

    def resolve_uploader_from_bvid(
        self,
        bvid: str,
    ) -> BilibiliUploaderIdentity:
        """
        用一个已经确认属于主播本人账号的
        BVID 反查 uploader MID。
        """

        bvid = (
            bvid.strip()
        )

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
            f"{VIEW_API}"
            f"?{query}"
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

        payload = data.get(
            "data",
            {},
        )

        owner = payload.get(
            "owner",
            {},
        )

        mid = owner.get(
            "mid"
        )

        display_name = str(
            owner.get(
                "name",
                "",
            )
        ).strip()

        if mid is None:
            raise BilibiliApiError(
                "Bilibili video response "
                "does not contain owner.mid"
            )

        if not display_name:
            raise BilibiliApiError(
                "Bilibili video response "
                "does not contain owner.name"
            )

        return (
            BilibiliUploaderIdentity(
                mid=int(mid),
                display_name=(
                    display_name
                ),
            )
        )

    def list_upload_page(
        self,
        *,
        mid: int,
        page_number: int,
        page_size: int = 50,
        keyword: str = "",
    ) -> BilibiliUploadPage:
        """
        使用 series/recArchivesByKeywords
        枚举 UP 投稿。

        与 space/wbi/arc/search 相比：

        - 不需要 WBI 签名
        - 不依赖空间页浏览器指纹
        - 更适合当前 Known VTuber inventory
        """

        if mid <= 0:
            raise ValueError(
                "mid must be positive"
            )

        if page_number < 1:
            raise ValueError(
                "page_number must be >= 1"
            )

        if not (
            1
            <= page_size
            <= 100
        ):
            raise ValueError(
                "page_size must be "
                "between 1 and 100"
            )

        params = {
            "mid": mid,
            "keywords": (
                keyword.strip()
            ),
            "pn": page_number,
            "ps": page_size,
            "orderby": "pubdate",
        }

        query = (
            urllib.parse.urlencode(
                params
            )
        )

        url = (
            f"{REPLAY_LIST_API}"
            f"?{query}"
        )

        last_error: (
            Exception
            | None
        ) = None

        for attempt in range(3):
            try:
                data = (
                    self._request_json(
                        url,
                        referer=(
                            "https://space."
                            "bilibili.com/"
                            f"{mid}/video"
                        ),
                    )
                )

                break

            except BilibiliApiError as exc:
                last_error = exc

                if attempt == 2:
                    raise

                time.sleep(
                    2.0
                    * (attempt + 1)
                )

        else:
            assert (
                last_error
                is not None
            )

            raise last_error

        if data.get("code") != 0:
            raise BilibiliApiError(
                "Bilibili replay list "
                "API failed: "
                f"code={data.get('code')}, "
                f"message="
                f"{data.get('message')}"
            )

        return (
            self._parse_upload_page(
                data=data,
                page_number=(
                    page_number
                ),
                page_size=(
                    page_size
                ),
            )
        )

    def _parse_upload_page(
        self,
        *,
        data: dict,
        page_number: int,
        page_size: int,
    ) -> BilibiliUploadPage:
        payload = (
            data.get(
                "data",
                {},
            )
            or {}
        )

        raw_items = (
            payload.get(
                "archives",
                [],
            )
            or []
        )

        page_payload = (
            payload.get(
                "page",
                {},
            )
            or {}
        )

        if not isinstance(
            raw_items,
            list,
        ):
            raise BilibiliApiError(
                "Invalid Bilibili replay "
                "list response"
            )

        items: list[
            BilibiliUpload
        ] = []

        for item in raw_items:
            bvid = str(
                item.get(
                    "bvid",
                    "",
                )
            ).strip()

            title = str(
                item.get(
                    "title",
                    "",
                )
            ).strip()

            if not bvid:
                continue

            duration = item.get(
                "duration",
                0,
            )

            if isinstance(
                duration,
                int,
            ):
                length = str(
                    duration
                )

            else:
                length = str(
                    duration or ""
                )

            items.append(
                BilibiliUpload(
                    aid=int(
                        item.get(
                            "aid",
                            0,
                        )
                    ),
                    bvid=bvid,
                    title=title,
                    created=int(
                        item.get(
                            "pubdate",
                            item.get(
                                "ctime",
                                0,
                            ),
                        )
                    ),
                    length=length,
                    author="",
                )
            )

        total = int(
            page_payload.get(
                "total",
                page_payload.get(
                    "count",
                    len(items),
                ),
            )
        )

        actual_page_number = int(
            page_payload.get(
                "page_num",
                page_payload.get(
                    "num",
                    page_number,
                ),
            )
        )

        actual_page_size = int(
            page_payload.get(
                "page_size",
                page_payload.get(
                    "size",
                    page_size,
                ),
            )
        )

        return (
            BilibiliUploadPage(
                items=items,
                total=total,
                page_number=(
                    actual_page_number
                ),
                page_size=(
                    actual_page_size
                ),
            )
        )

    def list_recent_replays(
        self,
        *,
        mid: int,
        since_timestamp: int,
        keyword: str = "直播回放",
        page_size: int = 50,
        page_delay: float = 1.0,
        max_pages: int | None = None,
    ) -> list[BilibiliUpload]:
        """
        按发布时间倒序枚举近期直播回放。

        一旦当前页已经进入 cutoff 之前，
        就停止继续翻更老页面。
        """

        if since_timestamp < 0:
            raise ValueError(
                "since_timestamp "
                "must be >= 0"
            )

        if (
            max_pages is not None
            and max_pages < 1
        ):
            raise ValueError(
                "max_pages must be >= 1"
            )

        results: list[
            BilibiliUpload
        ] = []

        seen_bvids: set[
            str
        ] = set()

        page_number = 1

        while True:
            page = (
                self.list_upload_page(
                    mid=mid,
                    page_number=(
                        page_number
                    ),
                    page_size=(
                        page_size
                    ),
                    keyword=(
                        keyword
                    ),
                )
            )

            if not page.items:
                break

            for item in page.items:
                if (
                    item.created
                    < since_timestamp
                ):
                    continue

                if not is_replay_title(
                    item.title,
                    keyword=keyword,
                ):
                    continue

                if (
                    item.bvid
                    in seen_bvids
                ):
                    continue

                seen_bvids.add(
                    item.bvid
                )

                results.append(
                    item
                )

            created_values = [
                item.created
                for item
                in page.items
                if item.created > 0
            ]

            if (
                created_values
                and min(
                    created_values
                )
                < since_timestamp
            ):
                break

            if (
                page_number
                * page.page_size
                >= page.total
            ):
                break

            if (
                max_pages is not None
                and page_number
                >= max_pages
            ):
                break

            page_number += 1

            if page_delay > 0:
                time.sleep(
                    page_delay
                )

        results.sort(
            key=lambda item:
                item.created,
            reverse=True,
        )

        return results