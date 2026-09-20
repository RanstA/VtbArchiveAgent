from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import Literal

from fastapi import (
    APIRouter,
    Query,
)
from pydantic import (
    BaseModel,
)

from app.config.settings import (
    settings,
)
from app.repository.database import (
    connect_db,
)
from app.repository.stream_repo import (
    list_streams,
)


router = APIRouter(
    prefix="/streams",
    tags=["streams"],
)


class StreamResponse(
    BaseModel
):
    id: str

    # 明确暴露 Stream 所属 VTuber。
    #
    # Phase 2B 前端可以利用这个字段
    # 校验 workspace scope。
    vtuberId: str
    vtuberName: str

    title: str
    liveTime: str
    bvIds: list[str]

    hasDanmaku: bool

    # TODO:
    # 前端旧 Event model 尚未迁移，
    # 暂时保留以避免当前页面破坏。
    hasEvents: bool

    durationMs: int | None = None


def normalize_live_time(
    value: str,
) -> str:
    """
    当前数据库中的历史 CSV 时间
    可能没有 timezone 信息。

    无 timezone 时按北京时间解释，
    并统一输出 ISO 8601。
    """

    dt = datetime.fromisoformat(
        value
    )

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone(
                timedelta(
                    hours=8
                )
            )
        )

    return dt.isoformat()


@router.get(
    "",
    response_model=list[
        StreamResponse
    ],
)
def get_streams(
    query: str | None = Query(
        default=None
    ),
    status: Literal[
        "danmaku",
        "events",
        "pending",
    ]
    | None = Query(
        default=None
    ),
    vtuber_id: str
    | None = Query(
        default=None,
        min_length=1,
        pattern=r".*\S.*",
    ),
):
    """
    查询 Stream。

    vtuber_id 未提供：
        返回所有 VTuber 的 Stream。

    vtuber_id 已提供：
        只返回指定 VTuber 的 Stream。

    Phase 2B 前端的 VTuber Workspace
    将始终携带该参数。
    """

    vtuber_filter = (
        vtuber_id.strip()
        if vtuber_id
        is not None
        else None
    )

    connection = connect_db(
        settings.database_path
    )

    try:
        rows = list_streams(
            connection=connection,
            query=query,
            vtuber_id=(
                vtuber_filter
            ),
        )

    finally:
        connection.close()

    result: list[
        StreamResponse
    ] = []

    for row in rows:
        # TODO:
        # 当前 frontend 仍使用旧 Event 状态，
        # Phase 3 迁移 Highlight API 时统一移除。
        has_events = False

        if status == "danmaku":
            if not row[
                "has_danmaku"
            ]:
                continue

        elif status == "events":
            continue

        elif status == "pending":
            pass

        result.append(
            StreamResponse(
                id=row["id"],
                vtuberId=(
                    row["vtuber_id"]
                ),
                vtuberName=(
                    row["vtuber_name"]
                ),
                title=row["title"],
                liveTime=(
                    normalize_live_time(
                        row[
                            "live_time"
                        ]
                    )
                ),
                bvIds=row["bv_ids"],
                hasDanmaku=(
                    row[
                        "has_danmaku"
                    ]
                ),
                hasEvents=(
                    has_events
                ),
                durationMs=None,
            )
        )

    return result