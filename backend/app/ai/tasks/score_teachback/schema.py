from pydantic import BaseModel, Field

from app.ai.tasks.common import FlagSpec


class ScoreTeachbackInput(BaseModel):
    answer_native: str
    answer_en: str | None = None
    language: str
    red_flags: list[FlagSpec]
    pass_threshold: float = Field(default=0.75, ge=0.0, le=1.0)


class TeachBack(BaseModel):
    mentioned_flag_ids: list[str] = Field(default_factory=list)
    missed_flag_ids: list[str] = Field(default_factory=list)
    passed: bool
