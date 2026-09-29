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
from app.event_pipeline.timeline import (
    build_stream_timeline,
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

    localAnchorMs: int

    salienceScore: float
    
    title: str | None = None
    summary: str | None = None

    keywords: list[str]
    entities: list[str]

    evidenceRefs: list[str]

    sourceHighlightIds: list[str]


class TimelineResponse(BaseModel):
    streamId: str

    durationMs: int | None

    mergeGapMs: int

    items: list[TimelineItemResponse]


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
    connection = connect_db(settings.database_path)

    try:
        timeline = build_stream_timeline(
            connection=connection,
            stream_id=stream_id,
        )

        if timeline is None:
            raise HTTPException(
                status_code=404,
                detail=("Stream not found"),
            )

        return TimelineResponse(
            streamId=(timeline.stream_id),
            durationMs=(timeline.duration_ms),
            mergeGapMs=(timeline.merge_gap_ms),
            items=[
                TimelineItemResponse(
                    id=item.id,
                    streamId=(item.stream_id),
                    sourcePartIds=(item.source_part_ids),
                    startMs=(item.start_ms),
                    endMs=(item.end_ms),
                    anchorMs=(item.anchor_ms),
                    localAnchorMs=(item.local_anchor_ms),
                    salienceScore=(item.salience_score),
                    sourceHighlightIds=(item.source_highlight_ids),
                    title=item.title,
                    summary=item.summary,
                    keywords=item.keywords,
                    entities=item.entities,
                    evidenceRefs=item.evidence_refs,
                )
                for item in timeline.items
            ],
        )

    finally:
        connection.close()
