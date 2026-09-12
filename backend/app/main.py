from fastapi import FastAPI

from app.api.streams import router as streams_router
from app.config.settings import settings


app = FastAPI(
    title="VTuber Archive",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {
        "status": "ok",
    }


@app.get("/debug/data-root")
def data_root():
    return {
        "path": str(settings.archive_data_root),
        "exists": settings.archive_data_root.exists(),
    }


app.include_router(streams_router)