from fastapi import FastAPI

app = FastAPI(
    title="VTuber Archive",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}

from app.config.settings import settings


@app.get("/debug/data-root")
def data_root():
    return {
        "path": str(settings.archive_data_root),
        "exists": settings.archive_data_root.exists(),
    }