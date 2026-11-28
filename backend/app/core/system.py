"""GET /api/v1/system/status: which providers, channels and modules are running, and how."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.channels.registry import ChannelRegistry, ChannelStatus
from app.providers.base import ProviderStatus
from app.providers.registry import ProviderRegistry


class SystemStatus(BaseModel):
    mode: str  # configured PROVIDER_MODE
    key_not_set: bool  # true -> show the "Key not set, using demo mode" badge
    providers: list[ProviderStatus]
    channels: list[ChannelStatus]
    modules: list[str]


def build_system_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/system", tags=["ops"])

    @router.get("/status", response_model=SystemStatus)
    def system_status(request: Request) -> SystemStatus:
        providers: ProviderRegistry = request.app.state.providers
        channels: ChannelRegistry = request.app.state.channels
        return SystemStatus(
            mode=request.app.state.settings.provider_mode,
            key_not_set=providers.any_key_missing,
            providers=providers.statuses(),
            channels=channels.statuses(),
            modules=list(getattr(request.app.state, "modules", [])),
        )

    return router
