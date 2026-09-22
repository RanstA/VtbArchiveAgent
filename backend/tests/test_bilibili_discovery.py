from app.ingestion.bilibili_discovery import (
    BilibiliDiscoveryClient,
    BilibiliUpload,
    BilibiliUploadPage,
    is_replay_title,
)


def test_is_replay_title():
    assert (
        is_replay_title(
            "【直播回放】聊天+随机PVZ "
            "2023年12月20日20点场"
        )
        is True
    )

    assert (
        is_replay_title(
            "【3D LIVE】生日纪念"
        )
        is False
    )


class FakeUploaderClient(
    BilibiliDiscoveryClient
):
    def _request_json(
        self,
        url: str,
        *,
        referer: str | None = None,
    ) -> dict:
        assert (
            "x/web-interface/view"
            in url
        )

        return {
            "code": 0,
            "data": {
                "owner": {
                    "mid": 123456,
                    "name": "阿萨Aza",
                },
            },
        }


def test_resolve_uploader_from_bvid():
    client = (
        FakeUploaderClient()
    )

    uploader = (
        client
        .resolve_uploader_from_bvid(
            "BV1TEST"
        )
    )

    assert (
        uploader.mid
        == 123456
    )

    assert (
        uploader.display_name
        == "阿萨Aza"
    )


class FakeUploadPageClient(
    BilibiliDiscoveryClient
):
    def __init__(self):
        super().__init__()

        self.requested_pages = []

    def list_upload_page(
        self,
        *,
        mid: int,
        page_number: int,
        page_size: int = 30,
        keyword: str = "",
    ) -> BilibiliUploadPage:
        self.requested_pages.append(
            page_number
        )

        assert mid == 123456
        assert (
            keyword
            == "直播回放"
        )

        if page_number == 1:
            return (
                BilibiliUploadPage(
                    items=[
                        BilibiliUpload(
                            aid=1,
                            bvid="BV1NEW",
                            title=(
                                "【直播回放】"
                                "新直播"
                            ),
                            created=300,
                            length=(
                                "03:00:00"
                            ),
                            author=(
                                "阿萨Aza"
                            ),
                        ),
                        BilibiliUpload(
                            aid=2,
                            bvid="BV1OTHER",
                            title=(
                                "普通投稿"
                            ),
                            created=250,
                            length=(
                                "10:00"
                            ),
                            author=(
                                "阿萨Aza"
                            ),
                        ),
                    ],
                    total=3,
                    page_number=1,
                    page_size=2,
                )
            )

        return (
            BilibiliUploadPage(
                items=[
                    BilibiliUpload(
                        aid=3,
                        bvid="BV1OLD",
                        title=(
                            "【直播回放】"
                            "旧直播"
                        ),
                        created=50,
                        length=(
                            "04:00:00"
                        ),
                        author=(
                            "阿萨Aza"
                        ),
                    ),
                ],
                total=3,
                page_number=2,
                page_size=2,
            )
        )


def test_list_recent_replays_stops_at_cutoff():
    client = (
        FakeUploadPageClient()
    )

    result = (
        client.list_recent_replays(
            mid=123456,
            since_timestamp=100,
            keyword="直播回放",
            page_size=2,
            page_delay=0,
        )
    )

    assert [
        item.bvid
        for item
        in result
    ] == [
        "BV1NEW",
    ]

    assert (
        client.requested_pages
        == [
            1,
            2,
        ]
    )