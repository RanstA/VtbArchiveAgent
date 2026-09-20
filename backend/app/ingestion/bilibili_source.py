import re
import uuid
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import Literal
from app.domain.vtuber import (
    VtuberSource,
    Vtuber,
)
from app.domain.danmaku import Danmaku
from app.domain.stream import Stream, make_stream_id
from app.domain.stream_part import StreamPart
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
            
        self.vtuber= vtuber

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
                vtuber_id=self.vtuber.id,
                live_time = live_time,
                title = video.title,
            )
        )

        stream = Stream(
            id=stream_id,
            vtuber_id=self.vtuber.id,
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

        for remote_part in video.parts:
            part_id = (
                f"p"
                f"{remote_part.page_index}"
            )

            part = StreamPart(
                stream_id=stream_id,
                part_id=part_id,
                video_path=None,
                danmaku_path=None,
                xml_path=None,
            )

            parts.append(
                part
            )

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
            vtuber_sources=[vtuber_source],
            stream=stream,
            parts=parts,
            danmaku=danmaku,
            source_metadata={
                "bvid": video.bvid,
                "aid": video.aid,
                "owner": video.owner,
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