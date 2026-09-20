from fastapi import (
    APIRouter,
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
from app.repository.vtuber_repo import (
    list_vtubers,
)


router = APIRouter(
    prefix="/vtubers",
    tags=["vtubers"],
)


class VtuberResponse(
    BaseModel
):
    id: str
    displayName: str


@router.get(
    "",
    response_model=list[
        VtuberResponse
    ],
)
def get_vtubers():
    connection = connect_db(
        settings.database_path
    )

    try:
        vtubers = list_vtubers(
            connection=connection
        )

    finally:
        connection.close()

    return [
        VtuberResponse(
            id=vtuber.id,
            displayName=(
                vtuber.display_name
            ),
        )
        for vtuber in vtubers
    ]