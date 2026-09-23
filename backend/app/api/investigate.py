from fastapi import (
    APIRouter,
    HTTPException,
)

from pydantic import (
    Field,
)

from app.config.settings import (
    settings,
)
from app.investigation.event_scout import (
    EventScout,
    EventScoutError,
)
from app.investigation.model_client import (
    ModelClientError,
    OpenAICompatibleChatClient,
)
from app.investigation.models import (
    ApiModel,
    EventScoutResult,
)
from app.investigation.tools import (
    EventScoutTools,
)


router = APIRouter(
    prefix="/investigate",
    tags=[
        "investigate"
    ],
)


class InvestigateRequest(
    ApiModel
):
    vtuber_id: str = Field(
        min_length=1
    )

    query: str = Field(
        min_length=1
    )


@router.post(
    "",
    response_model=(
        EventScoutResult
    ),
)
def investigate(
    request: InvestigateRequest,
):
    base_url = (
        settings
        .event_scout_api_base_url
        or ""
    ).strip()

    model_name = (
        settings
        .event_scout_model
        or ""
    ).strip()

    api_key = (
        settings
        .event_scout_api_key
        or ""
    ).strip()

    if (
        not base_url
        or not model_name
    ):
        raise HTTPException(
            status_code=503,
            detail=(
                "Event Scout model is not configured. "
                "Set EVENT_SCOUT_API_BASE_URL "
                "and EVENT_SCOUT_MODEL in backend/.env."
            ),
        )

    model = (
        OpenAICompatibleChatClient(
            base_url=base_url,
            model=model_name,
            api_key=(
                api_key
                or None
            ),
            timeout_seconds=(
                settings
                .event_scout_timeout_seconds
            ),
        )
    )

    tools = (
        EventScoutTools(
            database_path=(
                settings
                .database_path
            ),
            vtuber_id=(
                request
                .vtuber_id
                .strip()
            ),
        )
    )

    scout = EventScout(
        model=model,
        tools=tools,
    )

    try:
        return scout.run(
            query=(
                request.query
            ),
            vtuber_id=(
                request
                .vtuber_id
                .strip()
            ),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc

    except (
        EventScoutError,
        ModelClientError,
    ) as exc:
        raise HTTPException(
            status_code=502,
            detail=str(
                exc
            ),
        ) from exc