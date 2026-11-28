from pydantic import BaseModel, ConfigDict, Field


class Schema(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class TranscriptOut(Schema):
    text: str
    language: str
    confidence: float | None


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    language: str = Field(min_length=2, max_length=8)
