from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.repository.database import connect_db
from app.repository.stream_repo import list_streams


router = APIRouter(
    prefix="/streams",
    tags=["streams"],
)

DB_PATH = Path("vtuber_archive.db")


class StreamResponse(BaseModel):
    id: str
    title: str
    liveTime: str
    bvIds: list[str]

    hasDanmaku: bool
    hasEvents: bool

    durationMs: int | None = None


def normalize_live_time(value: str) -> str:
    """
    CSV 中当前时间没有 timezone 信息。
    直播时间按北京时间解释，并输出 +08:00 ISO 8601。
    """
    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone(
                timedelta(hours=8)
            )
        )

    return dt.isoformat()


@router.get(
    "",
    response_model=list[StreamResponse],
)
def get_streams(
    query: str | None = Query(default=None),
    status: Literal[
        "danmaku",
        "events",
        "pending",
    ]
    | None = Query(default=None),
):
    connection = connect_db(DB_PATH)

    try:
        rows = list_streams(
            connection=connection,
            query=query,
        )
    finally:
        connection.close()

    result: list[StreamResponse] = []

    for row in rows:
        # 当前 V0 尚未建立 Event Store
        has_events = False

        if status == "danmaku":
            if not row["has_danmaku"]:
                continue

        elif status == "events":
            # 当前还不存在 Event
            continue

        elif status == "pending":
            # 当前所有 Stream 都还没有 Event
            pass

        result.append(
            StreamResponse(
                id=row["id"],
                title=row["title"],
                liveTime=normalize_live_time(
                    row["live_time"]
                ),
                bvIds=row["bv_ids"],
                hasDanmaku=row["has_danmaku"],
                hasEvents=has_events,
                durationMs=None,
            )
        )

    return result