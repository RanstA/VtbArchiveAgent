import urllib.parse

from app.ingestion.bilibili_discovery import (
    BilibiliDiscoveryClient,
    BilibiliUpload,
    BilibiliUploadPage,
    is_replay_title,
)


def test_is_replay_title():
    assert is_replay_title("【直播回放】聊天+随机PVZ " "2023年12月20日20点场") is True

    assert is_replay_title("【3D LIVE】生日纪念") is False


class FakeUploaderClient(BilibiliDiscoveryClient):
    def _request_json(
        self,
        url: str,
        *,
        referer: str | None = None,
    ) -> dict:
        assert "x/web-interface/view" in url

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
    client = FakeUploaderClient()

    uploader = client.resolve_uploader_from_bvid("BV1TEST")

    assert uploader.mid == 123456

    assert uploader.display_name == "阿萨Aza"


class FakeUploadPageClient(BilibiliDiscoveryClient):
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
        self.requested_pages.append(page_number)

        assert mid == 123456

        assert keyword == "直播回放"

        if page_number == 1:
            return BilibiliUploadPage(
                items=[
                    BilibiliUpload(
                        aid=1,
                        bvid="BV1NEW",
                        title=("【直播回放】" "新直播"),
                        created=300,
                        length=("03:00:00"),
                        author=("阿萨Aza"),
                    ),
                    BilibiliUpload(
                        aid=2,
                        bvid="BV1OTHER",
                        title=("普通投稿"),
                        created=250,
                        length=("10:00"),
                        author=("阿萨Aza"),
                    ),
                ],
                total=3,
                page_number=1,
                page_size=2,
            )

        return BilibiliUploadPage(
            items=[
                BilibiliUpload(
                    aid=3,
                    bvid="BV1OLD",
                    title=("【直播回放】" "旧直播"),
                    created=50,
                    length=("04:00:00"),
                    author=("阿萨Aza"),
                ),
            ],
            total=3,
            page_number=2,
            page_size=2,
        )


def test_list_recent_replays_stops_at_cutoff():
    client = FakeUploadPageClient()

    result = client.list_recent_replays(
        mid=123456,
        since_timestamp=100,
        keyword="直播回放",
        page_size=2,
        page_delay=0,
    )

    assert [item.bvid for item in result] == [
        "BV1NEW",
    ]

    assert client.requested_pages == [
        1,
        2,
    ]


class FakeSeriesRequestClient(BilibiliDiscoveryClient):
    def _request_json(
        self,
        url: str,
        *,
        referer: str | None = None,
    ) -> dict:
        assert "x/series/archives" in url

        parsed = urllib.parse.urlparse(url)

        query = urllib.parse.parse_qs(parsed.query)

        assert query["mid"] == ["480680646"]

        assert query["series_id"] == ["61332"]

        assert query["pn"] == ["1"]

        assert query["ps"] == ["50"]

        assert query["only_normal"] == ["true"]

        assert query["sort"] == ["desc"]

        assert referer == (
            "https://space." "bilibili.com/" "480680646/lists/" "61332?type=series"
        )

        return {
            "code": 0,
            "message": "0",
            "data": {
                "archives": [
                    {
                        "aid": 1001,
                        "bvid": ("BV1SERIES"),
                        "title": ("标题不需要包含" "直播回放"),
                        "pubdate": 300,
                        "duration": 7200,
                    },
                ],
                "page": {
                    "num": 1,
                    "size": 50,
                    "total": 1,
                },
            },
        }


def test_list_series_page():
    client = FakeSeriesRequestClient()

    page = client.list_series_page(
        mid=480680646,
        series_id=61332,
        page_number=1,
        page_size=50,
        sort="desc",
    )

    assert page.total == 1

    assert page.page_number == 1

    assert page.page_size == 50

    assert len(page.items) == 1

    item = page.items[0]

    assert item.aid == 1001

    assert item.bvid == "BV1SERIES"

    assert item.title == ("标题不需要包含" "直播回放")

    assert item.created == 300

    assert item.length == "7200"


class FakeSeriesPageClient(BilibiliDiscoveryClient):
    def __init__(self):
        super().__init__()

        self.requested_pages = []

    def list_series_page(
        self,
        *,
        mid: int,
        series_id: int,
        page_number: int,
        page_size: int = 50,
        sort: str = "desc",
    ) -> BilibiliUploadPage:
        self.requested_pages.append(page_number)

        assert mid == 480680646

        assert series_id == 61332

        assert page_size == 2

        assert sort == "desc"

        if page_number == 1:
            return BilibiliUploadPage(
                items=[
                    BilibiliUpload(
                        aid=1,
                        bvid="BV1NEW",
                        title=("最新一场"),
                        created=300,
                        length="7200",
                        author="",
                    ),
                    BilibiliUpload(
                        aid=2,
                        bvid="BV1MIDDLE",
                        title=("普通标题也收"),
                        created=200,
                        length="7000",
                        author="",
                    ),
                ],
                total=3,
                page_number=1,
                page_size=2,
            )

        return BilibiliUploadPage(
            items=[
                BilibiliUpload(
                    aid=3,
                    bvid="BV1OLD",
                    title=("最早一场"),
                    created=100,
                    length="6800",
                    author="",
                ),
            ],
            total=3,
            page_number=2,
            page_size=2,
        )


def test_list_series_replays_reads_all_pages():
    client = FakeSeriesPageClient()

    result = client.list_series_replays(
        mid=480680646,
        series_id=61332,
        page_size=2,
        page_delay=0,
    )

    assert [item.bvid for item in result] == [
        "BV1NEW",
        "BV1MIDDLE",
        "BV1OLD",
    ]

    assert client.requested_pages == [
        1,
        2,
    ]


def test_list_series_replays_does_not_filter_title():
    client = FakeSeriesPageClient()

    result = client.list_series_replays(
        mid=480680646,
        series_id=61332,
        page_size=2,
        page_delay=0,
    )

    titles = [item.title for item in result]

    assert "普通标题也收" in titles
