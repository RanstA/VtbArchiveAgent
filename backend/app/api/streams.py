from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import Literal

from fastapi import (
    APIRouter,
    HTTPException,
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
from app.repository.highlight_repo import (
    list_highlights_by_stream,
)
from app.repository.stream_part_repo import (
    list_stream_parts,
)
from app.repository.stream_repo import (
    get_stream_by_id,
    list_streams,
)

from app.domain.event import (
    make_event_id,
)
from app.event_pipeline.events import (
    DEFAULT_MERGE_GAP_MS,
    merge_highlights,
)

router = APIRouter(
    prefix="/streams",
    tags=["streams"],
)


class StreamResponse(BaseModel):
    id: str

    vtuberId: str
    vtuberName: str

    title: str
    liveTime: str
    bvIds: list[str]

    hasDanmaku: bool

    hasHighlights: bool
    highlightCount: int

    durationMs: int | None = None


class StreamDetailResponse(StreamResponse):
    partCount: int


class HighlightResponse(BaseModel):
    id: str

    streamId: str
    partId: str

    startMs: int
    endMs: int
    peakMs: int

    score: float

    densityScore: float
    repetitionScore: float
    reactionScore: float

    danmakuCount: int
    uniqueTextCount: int

    repetitionRatio: float
    reactionRatio: float

    laughCount: int
    questionCount: int
    exclamationCount: int

    detectorVersion: str

class TimelineItemResponse(BaseModel):
    id: str

    streamId: str

    sourcePartIds: list[str]

    startMs: int
    endMs: int
    anchorMs: int

    salienceScore: float

    sourceHighlightIds: list[str]
    
class TimelineResponse(BaseModel):
    streamId: str

    durationMs: int | None

    mergeGapMs: int

    items: list[
        TimelineItemResponse
    ]

def normalize_live_time(
    value: str,
) -> str:
    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))

    return dt.isoformat()


def to_stream_response(
    row: dict,
) -> StreamResponse:
    highlight_count = int(row["highlight_count"])

    return StreamResponse(
        id=row["id"],
        vtuberId=(row["vtuber_id"]),
        vtuberName=(row["vtuber_name"]),
        title=row["title"],
        liveTime=(normalize_live_time(row["live_time"])),
        bvIds=row["bv_ids"],
        hasDanmaku=(row["has_danmaku"]),
        hasHighlights=(highlight_count > 0),
        highlightCount=(highlight_count),
        durationMs=None,
    )


@router.get(
    "",
    response_model=list[StreamResponse],
)
def get_streams(
    query: str | None = Query(default=None),
    status: (
        Literal[
            "danmaku",
            "highlights",
            "pending",
        ]
        | None
    ) = Query(default=None),
    vtuber_id: str | None = Query(
        default=None,
        min_length=1,
        pattern=r".*\S.*",
    ),
):
    vtuber_filter = vtuber_id.strip() if vtuber_id is not None else None

    connection = connect_db(settings.database_path)

    try:
        rows = list_streams(
            connection=connection,
            query=query,
            vtuber_id=(vtuber_filter),
        )

    finally:
        connection.close()

    result: list[StreamResponse] = []

    for row in rows:
        highlight_count = int(row["highlight_count"])

        if status == "danmaku":
            if not row["has_danmaku"]:
                continue

        elif status == "highlights":
            if highlight_count <= 0:
                continue

        elif status == "pending":
            if highlight_count > 0:
                continue

        result.append(to_stream_response(row))

    return result


@router.get(
    "/{stream_id}",
    response_model=(StreamDetailResponse),
)
def get_stream(
    stream_id: str,
):
    connection = connect_db(settings.database_path)

    try:
        row = get_stream_by_id(
            connection=connection,
            stream_id=stream_id,
        )

        if row is None:
            raise HTTPException(
                status_code=404,
                detail=("Stream not found"),
            )

        parts = list_stream_parts(
            connection=connection,
            stream_id=stream_id,
        )

        base = to_stream_response(row)

        return StreamDetailResponse(
            **base.model_dump(),
            partCount=len(parts),
        )

    finally:
        connection.close()


@router.get(
    "/{stream_id}/highlights",
    response_model=list[HighlightResponse],
)
def get_stream_highlights(
    stream_id: str,
):
    connection = connect_db(settings.database_path)

    try:
        stream = get_stream_by_id(
            connection=connection,
            stream_id=stream_id,
        )

        if stream is None:
            raise HTTPException(
                status_code=404,
                detail=("Stream not found"),
            )

        highlights = list_highlights_by_stream(
            connection=connection,
            stream_id=stream_id,
        )

        return [
            HighlightResponse(
                id=item.id,
                streamId=(item.stream_id),
                partId=(item.part_id),
                startMs=(item.start_ms),
                endMs=(item.end_ms),
                peakMs=(item.peak_ms),
                score=item.score,
                densityScore=(item.density_score),
                repetitionScore=(item.repetition_score),
                reactionScore=(item.reaction_score),
                danmakuCount=(item.danmaku_count),
                uniqueTextCount=(item.unique_text_count),
                repetitionRatio=(item.repetition_ratio),
                reactionRatio=(item.reaction_ratio),
                laughCount=(item.laugh_count),
                questionCount=(item.question_count),
                exclamationCount=(item.exclamation_count),
                detectorVersion=(item.detector_version),
            )
            for item in highlights
        ]

    finally:
        connection.close()


@router.get(
    "/{stream_id}/timeline",
    response_model=TimelineResponse,
)
def get_stream_timeline(
    stream_id: str,
):
    """
    当前 Timeline MVP。

    Highlight / EventCandidate 仍然使用
    Part-local 时间。

    这里在 Product Serving 边界统一转换为
    Stream-global 时间：

        global_ms
        =
        part.start_offset_ms
        +
        local_ms

    当前 Timeline Item 只代表
    audience-reaction 高光片段，

    尚不是完整的 semantic Event。
    """

    connection = connect_db(
        settings.database_path
    )

    try:
        stream = get_stream_by_id(
            connection=connection,
            stream_id=stream_id,
        )

        if stream is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Stream not found"
                ),
            )

        parts = list_stream_parts(
            connection=connection,
            stream_id=stream_id,
        )

        highlights = (
            list_highlights_by_stream(
                connection=connection,
                stream_id=stream_id,
            )
        )

        part_by_id = {
            part["part_id"]: part
            for part in parts
        }

        highlight_by_id = {
            highlight.id: highlight
            for highlight in highlights
        }

        candidates = merge_highlights(
            highlights,
            merge_gap_ms=(
                DEFAULT_MERGE_GAP_MS
            ),
        )

        items: list[
            TimelineItemResponse
        ] = []

        for candidate in candidates:
            part = part_by_id.get(
                candidate.part_id
            )

            if part is None:
                raise RuntimeError(
                    "Timeline candidate "
                    "references unknown part: "
                    f"{candidate.part_id}"
                )

            offset_ms = int(
                part[
                    "start_offset_ms"
                ]
            )

            start_ms = (
                offset_ms
                + candidate.start_ms
            )

            end_ms = (
                offset_ms
                + candidate.end_ms
            )

            anchor_ms = (
                offset_ms
                + candidate.peak_ms
            )

            source_highlights = [
                highlight_by_id[
                    highlight_id
                ]
                for highlight_id
                in (
                    candidate
                    .source_highlight_ids
                )
            ]

            salience_score = max(
                highlight.score
                for highlight
                in source_highlights
            )

            items.append(
                TimelineItemResponse(
                    id=make_event_id(
                        stream_id=(
                            stream_id
                        ),
                        start_ms=(
                            start_ms
                        ),
                        end_ms=end_ms,
                    ),
                    streamId=stream_id,
                    sourcePartIds=[
                        candidate.part_id
                    ],
                    startMs=start_ms,
                    endMs=end_ms,
                    anchorMs=(
                        anchor_ms
                    ),
                    salienceScore=(
                        salience_score
                    ),
                    sourceHighlightIds=[
                        (
                            highlight.id
                        )
                        for highlight
                        in source_highlights
                    ],
                )
            )

        items.sort(
            key=lambda item: (
                item.startMs,
                item.endMs,
            )
        )

        known_part_ends = [
            (
                int(
                    part[
                        "start_offset_ms"
                    ]
                )
                + int(
                    part[
                        "duration_ms"
                    ]
                )
            )
            for part in parts
            if (
                part[
                    "duration_ms"
                ]
                is not None
            )
        ]

        timeline_end = max(
            (
                item.endMs
                for item in items
            ),
            default=0,
        )

        duration_ms = max(
            [
                *known_part_ends,
                timeline_end,
            ],
            default=0,
        )

        return TimelineResponse(
            streamId=stream_id,
            durationMs=(
                duration_ms
                if duration_ms > 0
                else None
            ),
            mergeGapMs=(
                DEFAULT_MERGE_GAP_MS
            ),
            items=items,
        )

    finally:
        connection.close()