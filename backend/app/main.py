"""CareVoice API and static React app, served together on one port."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import Settings, get_settings

logger = logging.getLogger("carevoice")

FALLBACK_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>CareVoice</title></head>
<body style="font-family: system-ui; padding: 2rem">
<h1>CareVoice</h1>
<p>The API is running, but the frontend has not been built yet.</p>
<p>Run <code>cd frontend &amp;&amp; npm run build</code>,
or use <code>docker compose up --build</code>.</p>
</body></html>"""


def build_api_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": settings.provider_mode, "version": settings.version}

    return router


def mount_frontend(app: FastAPI, static_dir: Path) -> None:
    """Serve the React build; any non-API path returns index.html (client-side routing)."""
    index = static_dir / "index.html"
    assets = static_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    def spa(full_path: str) -> FileResponse | HTMLResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (static_dir / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(static_dir.resolve()):
            return FileResponse(candidate)
        if index.is_file():
            return FileResponse(index)
        return HTMLResponse(FALLBACK_PAGE)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.warning("CareVoice ready on :%s (%s mode)", settings.port, settings.provider_mode)
        yield

    app = FastAPI(
        title="CareVoice API",
        version=settings.version,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(build_api_router(settings))
    mount_frontend(app, settings.static_dir)
    return app


app = create_app()
