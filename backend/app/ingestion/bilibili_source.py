import re
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import Literal

from app.domain.danmaku import Danmaku
from app.domain.stream import (
    Stream,
    make_stream_id,
)
from app.domain.stream_part import (
    StreamPart,
)
from app.domain.vtuber import (
    Vtuber,
    VtuberSource,
)
from app.ingestion.bilibili_client import (
    BilibiliClient,
    BilibiliVideoInfo,
)
from app.ingestion.bilibili_session import (
    BilibiliSessionStore,
)
from app.ingestion.source import (
    ArchiveBundle,
)


AuthMode = Literal[
    "auto",
    "guest",
    "authenticated",
]


CHINA_TZ = timezone(
    timedelta(
        hours=8
    )
)


LIVE_TIME_PATTERN = re.compile(
    r"(?P<year>20\d{2})年"
    r"(?P<month>\d{1,2})月"
    r"(?P<day>\d{1,2})日"
    r"(?P<hour>\d{1,2})点"
)


class BilibiliAuthenticationError(
    RuntimeError
):
    pass


def _timestamp_to_china_datetime(
    timestamp: int,
) -> datetime:
    return (
        datetime.fromtimestamp(
            timestamp,
            tz=CHINA_TZ,
        )
        .replace(
            tzinfo=None
        )
    )


def infer_live_time(
    video: BilibiliVideoInfo,
) -> tuple[datetime, str]:
    """
    优先从直播回放标题识别真正直播时间。

    返回：
        (live_time, inference_basis)
    """

    match = LIVE_TIME_PATTERN.search(
        video.title
    )

    if match:
        return (
            datetime(
                year=int(
                    match.group(
                        "year"
                    )
                ),
                month=int(
                    match.group(
                        "month"
                    )
                ),
                day=int(
                    match.group(
                        "day"
                    )
                ),
                hour=int(
                    match.group(
                        "hour"
                    )
                ),
            ),
            "title",
        )

    return (
        _timestamp_to_china_datetime(
            video.pubdate
        ),
        "pubdate",
    )


class BilibiliSource:
    """
    Bilibili Archive Source。
    """

    def __init__(
        self,
        bvid: str,
        *,
        vtuber: Vtuber,
        auth_mode: AuthMode = "auto",
        session_store: (
            BilibiliSessionStore
            | None
        ) = None,
        client: (
            BilibiliClient
            | None
        ) = None,
    ) -> None:
        self.bvid = bvid.strip()

        if not self.bvid:
            raise ValueError(
                "bvid cannot be empty"
            )

        if auth_mode not in {
            "auto",
            "guest",
            "authenticated",
        }:
            raise ValueError(
                "Invalid auth_mode: "
                f"{auth_mode}"
            )

        self.vtuber = vtuber

        self.auth_mode = (
            auth_mode
        )

        self.session_store = (
            session_store
            if session_store
            is not None
            else BilibiliSessionStore()
        )

        self._provided_client = (
            client
        )

    def _build_client(
        self,
    ) -> tuple[
        BilibiliClient,
        bool,
    ]:
        if (
            self._provided_client
            is not None
        ):
            return (
                self._provided_client,
                bool(
                    self._provided_client
                    .authenticated
                ),
            )

        if self.auth_mode == "guest":
            return (
                BilibiliClient(),
                False,
            )

        session = (
            self.session_store.load()
        )

        if session is None:
            if (
                self.auth_mode
                == "authenticated"
            ):
                raise (
                    BilibiliAuthenticationError(
                        "No valid Bilibili "
                        "session found"
                    )
                )

            return (
                BilibiliClient(),
                False,
            )

        authenticated_client = (
            BilibiliClient(
                sessdata=(
                    session.sessdata
                )
            )
        )

        if (
            authenticated_client
            .is_authenticated()
        ):
            return (
                authenticated_client,
                True,
            )

        # Bilibili token 比本地 TTL
        # 更早失效时，主动清理缓存。
        self.session_store.clear()

        if (
            self.auth_mode
            == "authenticated"
        ):
            raise (
                BilibiliAuthenticationError(
                    "Cached Bilibili "
                    "session is no longer "
                    "valid"
                )
            )

        return (
            BilibiliClient(),
            False,
        )

    def load(
        self,
    ) -> ArchiveBundle:
        client, authenticated = (
            self._build_client()
        )

        video = (
            client.get_video_info(
                self.bvid
            )
        )

        live_time, live_time_basis = (
            infer_live_time(
                video
            )
        )

        publish_time = (
            _timestamp_to_china_datetime(
                video.pubdate
            )
        )

        stream_id = (
            make_stream_id(
                vtuber_id=(
                    self.vtuber.id
                ),
                live_time=live_time,
                title=video.title,
            )
        )

        stream = Stream(
            id=stream_id,
            vtuber_id=(
                self.vtuber.id
            ),
            month=(
                live_time.strftime(
                    "%Y-%m"
                )
            ),
            live_time=live_time,
            publish_times=[
                publish_time
            ],
            bv_ids=[
                video.bvid
            ],
            title=video.title,
            video_url=(
                video.video_url
            ),
            status="online",
        )

        parts: list[
            StreamPart
        ] = []

        danmaku: list[
            Danmaku
        ] = []

        # Bilibili 返回的弹幕时间仍然是
        # Part-local。
        #
        # StreamPart.start_offset_ms
        # 负责描述该 Part 在整场 Stream
        # 中的起点。
        #
        # 后续构造 Unified Event 时：
        #
        # stream_global_ms
        #   = start_offset_ms
        #   + part_local_ms
        start_offset_ms = 0

        ordered_parts = sorted(
            video.parts,
            key=lambda item:
                item.page_index,
        )

        for index, remote_part in enumerate(
            ordered_parts
        ):
            part_id = (
                f"p"
                f"{remote_part.page_index}"
            )

            duration_ms = (
                remote_part.duration_seconds
                * 1000
                if (
                    remote_part.duration_seconds
                    > 0
                )
                else None
            )

            # 如果当前不是最后一个 Part，
            # 就必须知道它的 duration，
            # 否则无法计算后续 Part 的
            # Stream-global offset。
            if (
                duration_ms is None
                and index
                < len(ordered_parts) - 1
            ):
                raise RuntimeError(
                    "Cannot calculate "
                    "stream-global offsets: "
                    f"{part_id} has no duration"
                )

            part = StreamPart(
                stream_id=stream_id,
                part_id=part_id,
                start_offset_ms=(
                    start_offset_ms
                ),
                duration_ms=(
                    duration_ms
                ),
                video_path=None,
                danmaku_path=None,
                xml_path=None,
            )

            parts.append(
                part
            )

            # 注意：
            # 即使最后一个 Part 的
            # duration 未知，
            # 仍然应该读取它的弹幕。
            remote_danmaku = (
                client.get_part_danmaku(
                    video=video,
                    part=remote_part,
                )
            )

            for item in remote_danmaku:
                danmaku.append(
                    Danmaku(
                        stream_id=(
                            stream_id
                        ),
                        part_id=part_id,
                        timestamp_ms=(
                            item.timestamp_ms
                        ),
                        raw_text=(
                            item.text
                        ),
                        text=(
                            item.text
                        ),
                    )
                )

            # 当前 Part 完成后，
            # 为下一个 Part 推进
            # Stream-global offset。
            if duration_ms is not None:
                start_offset_ms += (
                    duration_ms
                )

        vtuber_source = (
            VtuberSource(
                vtuber_id=(
                    self.vtuber.id
                ),
                source="bilibili",
                external_id=None,
                display_name=(
                    video.owner
                ),
            )
        )

        return ArchiveBundle(
            source="bilibili",
            vtuber=self.vtuber,
            vtuber_sources=[
                vtuber_source
            ],
            stream=stream,
            parts=parts,
            danmaku=danmaku,
            source_metadata={
                "bvid": (
                    video.bvid
                ),
                "aid": (
                    video.aid
                ),
                "owner": (
                    video.owner
                ),
                "authenticated": (
                    authenticated
                ),
                "auth_mode": (
                    self.auth_mode
                ),
                "live_time_basis": (
                    live_time_basis
                ),
                "part_count": (
                    len(parts)
                ),
                "danmaku_count": (
                    len(danmaku)
                ),
            },
        )