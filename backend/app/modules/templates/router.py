import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.ai.registry import run_task
from app.ai.tasks.extract_template.schema import ExtractTemplateInput
from app.core.context import current_doctor
from app.core.db import get_session
from app.modules.templates import service
from app.modules.templates.schemas import (
    TemplateDraft,
    TemplateExtractRequest,
    TemplateOut,
    TemplateSave,
    TemplateSummary,
)

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.get("", response_model=list[TemplateSummary])
def list_templates(session: Session = Depends(get_session)) -> list[TemplateSummary]:
    return service.list_templates(session, current_doctor(session))


@router.post("/extract", response_model=TemplateDraft)
async def extract_template(body: TemplateExtractRequest, request: Request) -> TemplateDraft:
    """Dictated template -> draft with unclear_fields. Nothing is saved."""
    result = await run_task(
        request.app.state.providers,
        "extract_template",
        ExtractTemplateInput(transcript=body.transcript),
    )
    return TemplateDraft(
        template=result.output, source=result.source, needs_review=result.needs_review
    )


@router.get("/{template_id}", response_model=TemplateOut)
def get_template(
    template_id: uuid.UUID,
    version: int | None = Query(default=None, ge=1),
    session: Session = Depends(get_session),
) -> TemplateOut:
    return service.get_template(session, current_doctor(session), template_id, version)


@router.post("", response_model=TemplateOut, status_code=201)
def save_template(body: TemplateSave, session: Session = Depends(get_session)) -> TemplateOut:
    return service.save_template(session, current_doctor(session), body)
