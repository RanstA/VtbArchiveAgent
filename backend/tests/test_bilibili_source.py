from app.domain.stream import (
    make_stream_id,
)
from app.domain.vtuber import (
    Vtuber,
)
from app.ingestion.bilibili_client import (
    BilibiliDanmakuItem,
    BilibiliPart,
    BilibiliVideoInfo,
)
from app.ingestion.bilibili_source import (
    BilibiliSource,
)


TEST_VTUBER = Vtuber(
    id="vtuber-test",
    display_name="TestVTuber",
)


class FakeBilibiliClient:
    def __init__(
        self,
        *,
        authenticated: bool = True,
    ):
        self.authenticated = (
            authenticated
        )

    def get_video_info(
        self,
        bvid: str,
    ) -> BilibiliVideoInfo:
        assert (
            bvid
            == "BV1TEST"
        )

        return BilibiliVideoInfo(
            aid=123,
            bvid="BV1TEST",
            title=(
                "【直播回放】测试直播 "
                "2026年08月16日21点场"
            ),
            owner="TestVTuber",
            pubdate=1755352800,
            video_url=(
                "https://www.bilibili.com/"
                "video/BV1TEST"
            ),
            parts=[
                BilibiliPart(
                    page_index=0,
                    cid=1001,
                    title="0-测试直播",
                    duration_seconds=7200,
                ),
                BilibiliPart(
                    page_index=1,
                    cid=1002,
                    title="1-测试直播",
                    duration_seconds=3600,
                ),
            ],
        )

    def get_part_danmaku(
        self,
        *,
        video,
        part,
    ) -> list[
        BilibiliDanmakuItem
    ]:
        if (
            part.page_index
            == 0
        ):
            return [
                BilibiliDanmakuItem(
                    dmid=1,
                    timestamp_ms=1000,
                    text="晚上好",
                    weight=2,
                ),
                BilibiliDanmakuItem(
                    dmid=2,
                    timestamp_ms=2000,
                    text="哈哈哈哈",
                    weight=10,
                ),
            ]

        return [
            BilibiliDanmakuItem(
                dmid=3,
                timestamp_ms=3000,
                text="第二P",
                weight=3,
            )
        ]


def test_bilibili_source_maps_to_domain():
    source = BilibiliSource(
        "BV1TEST",
        vtuber=TEST_VTUBER,
        client=(
            FakeBilibiliClient(
                authenticated=True
            )
        ),
    )

    bundle = source.load()

    assert (
        bundle.source
        == "bilibili"
    )

    assert (
        bundle.vtuber
        == TEST_VTUBER
    )

    assert (
        bundle.stream.vtuber_id
        == TEST_VTUBER.id
    )

    assert (
        bundle.stream.id
        == make_stream_id(
            vtuber_id=(
                TEST_VTUBER.id
            ),
            live_time=(
                bundle.stream.live_time
            ),
            title=(
                bundle.stream.title
            ),
        )
    )

    assert (
        len(
            bundle.vtuber_sources
        )
        == 1
    )

    vtuber_source = (
        bundle.vtuber_sources[0]
    )

    assert (
        vtuber_source.vtuber_id
        == TEST_VTUBER.id
    )

    assert (
        vtuber_source.source
        == "bilibili"
    )

    assert (
        vtuber_source.display_name
        == "TestVTuber"
    )

    assert (
        bundle.stream.title
        == (
            "【直播回放】测试直播 "
            "2026年08月16日21点场"
        )
    )

    assert (
        bundle.stream.live_time.year
        == 2026
    )

    assert (
        bundle.stream.live_time.month
        == 8
    )

    assert (
        bundle.stream.live_time.day
        == 16
    )

    assert (
        bundle.stream.live_time.hour
        == 21
    )

    assert len(
        bundle.parts
    ) == 2

    assert [
        part.part_id
        for part
        in bundle.parts
    ] == [
        "p0",
        "p1",
    ]

    assert len(
        bundle.danmaku
    ) == 3

    assert (
        bundle.danmaku[0]
        .timestamp_ms
        == 1000
    )

    assert (
        bundle.danmaku[0]
        .raw_text
        == "晚上好"
    )

    assert (
        bundle.danmaku[0]
        .text
        == "晚上好"
    )

    assert (
        bundle.source_metadata[
            "authenticated"
        ]
        is True
    )

    assert (
        bundle.source_metadata[
            "live_time_basis"
        ]
        == "title"
    )


def test_bilibili_source_keeps_parts_separate():
    source = BilibiliSource(
        "BV1TEST",
        vtuber=TEST_VTUBER,
        client=(
            FakeBilibiliClient()
        ),
    )

    bundle = source.load()

    part_ids = [
        item.part_id
        for item
        in bundle.danmaku
    ]

    assert part_ids == [
        "p0",
        "p0",
        "p1",
    ]