"""CareVoice API and static React app, served together on one port."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.ai.registry import install_demo_rules
from app.channels.registry import ChannelRegistry
from app.core.config import Settings, get_settings
from app.core.db import Database
from app.core.errors import register_error_handlers
from app.core.events import EventBus
from app.core.modules import load_modules
from app.core.system import build_system_router
from app.providers.registry import ProviderRegistry

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

    @app.api_route(
        "/api/{rest:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    def api_not_found(rest: str) -> None:
        raise HTTPException(status_code=404, detail="Not found")

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    def spa(full_path: str) -> FileResponse | HTMLResponse:
        candidate = (static_dir / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(static_dir.resolve()):
            return FileResponse(candidate)
        if index.is_file():
            return FileResponse(index)
        return HTMLResponse(FALLBACK_PAGE)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    db = Database(settings.database_url)
    bus = EventBus()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        drift = db.schema_drift()
        if drift and settings.demo_endpoints:
            # Demo data only: rebuild rather than crash on an old local database.
            logger.warning("Database schema changed (%s); recreating demo data", ", ".join(drift))
            db.drop_all()
        elif drift:
            raise RuntimeError(
                f"Database schema is out of date ({', '.join(drift)}); run migrations"
            )
        db.create_all()
        for hook in app.state.startup_hooks:
            hook(db, bus)
        tasks = [asyncio.create_task(loop()) for loop in app.state.background_loops]
        logger.warning(
            "CareVoice ready on :%s (%s mode, modules: %s)",
            settings.port,
            settings.provider_mode,
            ", ".join(app.state.modules) or "none",
        )
        yield
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        db.engine.dispose()

    app = FastAPI(
        title="CareVoice API",
        version=settings.version,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.bus = bus
    app.state.providers = ProviderRegistry(settings)
    install_demo_rules(app.state.providers)
    app.state.channels = ChannelRegistry(settings)
    app.state.startup_hooks = []
    app.state.background_loops = []

    register_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(build_api_router(settings))
    app.include_router(build_system_router())
    load_modules(app, bus, settings.module_names)
    # Last: the SPA catch-all must not shadow module routes.
    mount_frontend(app, settings.static_dir)
    return app


app = create_app()
