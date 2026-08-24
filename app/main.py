from __future__ import annotations

import time
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.api.context import router as context_router
from app.api.health import router as health_router
from app.api.metadata import router as metadata_router
from app.api.reply import router as reply_router
from app.api.tick import router as tick_router
from app.config import settings
from app.utils.logging import logger

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Vera — magicpin AI Challenge Submission",
    description="Stateful AI merchant/customer engagement bot for local commerce.",
    version=settings.bot_version,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_and_time_requests(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000.0
    logger.info(
        f"{request.method} {request.url.path} returned {response.status_code} in {duration_ms:.2f}ms"
    )
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal processing error occurred."},
    )


@app.post("/v1/reset")
def reset_all_stores():
    from app.services.context_store import context_store
    from app.services.conversation_store import conversation_store
    from app.services.suppression import suppression_engine
    from app.utils.timing import reset_uptime

    context_store.clear()
    conversation_store.clear()
    suppression_engine.clear()
    reset_uptime()
    return {"status": "ok", "message": "All stores and metrics reset successfully."}


# Include API routers
app.include_router(health_router)
app.include_router(metadata_router)
app.include_router(context_router)
app.include_router(tick_router)
app.include_router(reply_router)

# Serve static dashboard
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def dashboard():
    """Serve the Vera dashboard UI."""
    return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
