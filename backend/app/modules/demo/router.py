from fastapi import APIRouter, Request

from app.modules.demo import service
from app.modules.demo.schemas import ResetResult

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


@router.post("/reset", response_model=ResetResult)
def reset_demo(request: Request) -> ResetResult:
    """Restore the seeded demo data. Only available when DEMO_ENDPOINTS=true."""
    counts = service.reset(request.app.state.db, request.app.state.bus)
    return ResetResult(counts=counts)
