import ipaddress
import sqlite3

import httpx

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
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
from app.investigation.deep_research import DeepResearchAgent
from app.investigation.deep_research_models import (
    CitationGuardError, DeepResearchError, ResearchModel, ResearchReport,
)
from app.repository.vtuber_repo import get_vtuber


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


class ResearchRequest(ResearchModel):
    vtuber_id: str = Field(min_length=1)
    query: str = Field(min_length=1, max_length=1_000)


def require_research_dev_access(request: Request) -> None:
    if not settings.deep_research_dev_enabled:
        raise HTTPException(status_code=404, detail={
            "code": "research_disabled",
            "message": "研究接口未启用：仅供本地开发，在 backend/.env 设置 DEEP_RESEARCH_DEV_ENABLED=true 后重启。",
        })
    try:
        local = request.client is not None and ipaddress.ip_address(request.client.host).is_loopback
    except ValueError:
        local = False
    if not local:
        raise HTTPException(status_code=403, detail={
            "code": "research_local_only", "message": "研究接口仅允许本机开发访问。",
        })


def make_research_agent() -> DeepResearchAgent:
    base_url = (settings.event_scout_api_base_url or "").strip()
    model_name = (settings.event_scout_model or "").strip()
    if not base_url or not model_name:
        raise HTTPException(status_code=503, detail={
            "code": "model_not_configured",
            "message": "请配置 EVENT_SCOUT_API_BASE_URL 与 EVENT_SCOUT_MODEL。",
        })
    return DeepResearchAgent(model=OpenAICompatibleChatClient(
        base_url=base_url, model=model_name,
        api_key=(settings.event_scout_api_key or "").strip() or None,
        timeout_seconds=settings.event_scout_timeout_seconds,
    ))


@router.post(
    "/research", response_model=ResearchReport, response_model_by_alias=True,
    dependencies=[Depends(require_research_dev_access)],
    responses={
        403: {"description": "Local development only"},
        404: {"description": "Disabled or VTuber not found"},
        502: {"description": "Model/structured output/citation validation failure"},
        503: {"description": "Model or archive unavailable"},
        504: {"description": "Model timed out"},
    },
)
def research(request: ResearchRequest):
    agent = make_research_agent()
    connection = None
    try:
        # mode=ro prevents both writes and accidental creation of an empty DB.
        connection = sqlite3.connect(
            settings.database_path.resolve().as_uri() + "?mode=ro", uri=True,
        )
        if get_vtuber(connection, request.vtuber_id) is None:
            raise HTTPException(status_code=404, detail={
                "code": "vtuber_not_found", "message": "未找到指定主播。",
            })
        return agent.run(connection, query=request.query, vtuber_id=request.vtuber_id)
    except CitationGuardError as exc:
        raise HTTPException(status_code=502, detail={
            "code": "citation_validation_failed",
            "message": "引用校验失败，未返回未经验证的研究报告。",
        }) from exc
    except DeepResearchError as exc:
        cause = exc
        timeout = False
        while cause is not None:
            timeout = timeout or isinstance(cause, (TimeoutError, httpx.TimeoutException))
            cause = cause.__cause__
        raise HTTPException(status_code=504 if timeout else 502, detail={
            "code": "model_timeout" if timeout else "research_failed",
            "message": "模型请求超时，请稍后重试。" if timeout else f"研究失败：{exc}",
        }) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={
            "code": "invalid_research_request", "message": str(exc),
        }) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail={
            "code": "archive_unavailable", "message": "研究档案暂不可用，请检查本地数据库配置。",
        }) from exc
    finally:
        if connection is not None:
            connection.close()


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
