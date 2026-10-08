from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.config.settings import settings
from app.domain.evidence.danmaku import Danmaku
from app.domain.evidence.transcript_segment import TranscriptSegment
from app.domain.pipeline.topic_segment import TopicSegment
from app.product.search import SearchHit
from app.product.topic_evidence import (
    TopicEvidenceError,
    TopicNotFoundError,
    expand_topic_evidence,
)
from app.product.topic_search import search_topics
from app.repository.database import connect_db


router = APIRouter(prefix="/search", tags=["search"])

# Keep Domain/Product field names intact; only the HTTP projection is camelCase.
_RESPONSE_CONFIG = ConfigDict(
    alias_generator=to_camel, populate_by_name=True, from_attributes=True,
)


class SearchHitResponse(SearchHit):
    model_config = _RESPONSE_CONFIG


class TopicSegmentResponse(TopicSegment):
    model_config = _RESPONSE_CONFIG


class TranscriptSegmentResponse(TranscriptSegment):
    model_config = _RESPONSE_CONFIG


class DanmakuResponse(Danmaku):
    model_config = _RESPONSE_CONFIG


class TopicEvidenceResponse(BaseModel):
    model_config = _RESPONSE_CONFIG

    topic: TopicSegmentResponse
    transcripts: list[TranscriptSegmentResponse]
    danmaku: list[DanmakuResponse]


@router.get("/topics", response_model=list[SearchHitResponse])
def get_topic_search(
    q: str = Query(..., description="Literal keyword; blank queries return no hits."),
    vtuber_id: str | None = Query(default=None, min_length=1, pattern=r".*\S.*"),
    limit: int = Query(default=5, ge=1, le=100),
):
    connection = connect_db(settings.database_path)
    try:
        return search_topics(
            connection,
            query=q,
            vtuber_id=vtuber_id.strip() if vtuber_id is not None else None,
            limit=limit,
        )
    finally:
        connection.close()


@router.get(
    "/topics/{topic_segment_id}/evidence",
    response_model=TopicEvidenceResponse,
    responses={
        404: {"description": "TopicSegment not found"},
        409: {"description": "Stored evidence references are incomplete or inconsistent"},
    },
)
def get_topic_evidence(topic_segment_id: str):
    connection = connect_db(settings.database_path)
    try:
        # All related reads observe one SQLite snapshot during concurrent imports.
        connection.execute("BEGIN")
        return expand_topic_evidence(connection, topic_segment_id)
    except TopicNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TopicEvidenceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        connection.close()
