import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database.db import check_database, init_db
from app.database.vector_db import vector_db
from app.services.embeddings import embedding_service
from app.services.reranker import reranker_service
from app.api import documents, search, chat, compare, analytics

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        return json.dumps(payload)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO), handlers=[handler], force=True)
logger = logging.getLogger("docusense")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}...")
    init_db()
    if settings.MODEL_PRELOAD:
        embedding_service.start_loading()
        reranker_service.start_loading()
        logger.info("Model warmup started in %s mode", settings.MODEL_RUNTIME_MODE)
    yield
    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}...")
    # Model loaders are daemon threads. Do not join them during reload or shutdown;
    # in-flight downloads must not hold the server process open.

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Context-Aware Document Intelligence Using Hybrid and Temporal RAG",
    lifespan=lifespan
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled request error", extra={"request_id": request_id})
        raise
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "%s %s -> %s in %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started) * 1000,
        extra={"request_id": request_id},
    )
    return response

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(documents.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(compare.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")

# Static frontend directory configuration
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))

if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
def serve_root():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "DocuSense API running. Frontend folder not found."}

@app.get("/style.css")
def serve_css():
    css_path = os.path.join(frontend_dir, "style.css")
    return FileResponse(css_path, media_type="text/css")

@app.get("/app.js")
def serve_js():
    js_path = os.path.join(frontend_dir, "app.js")
    return FileResponse(js_path, media_type="application/javascript")

@app.get("/health/live", tags=["Health"])
def liveness_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
    }


@app.get("/health/ready", tags=["Health"])
def readiness_check():
    embedding_status = embedding_service.status()
    reranker_status = reranker_service.status()
    model_states = {embedding_status["status"], reranker_status["status"]}
    model_status = "error" if "failed" in model_states else ("ok" if model_states == {"ok"} else "loading")
    checks = {
        "database": check_database(),
        "vector_store": vector_db.health_check(),
        "models": {
            "status": model_status,
            "mode": settings.MODEL_RUNTIME_MODE,
            "embedding": embedding_status,
            "reranker": reranker_status,
        },
    }
    ready = all(check["status"] == "ok" for check in checks.values())
    body = {"status": "ready" if ready else "not_ready", "checks": checks}
    if not ready:
        return JSONResponse(status_code=503, content=body)
    return body


@app.get("/health", tags=["Health"])
def health_check():
    return readiness_check()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
