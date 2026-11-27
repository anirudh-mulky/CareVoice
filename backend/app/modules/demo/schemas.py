from pydantic import BaseModel


class ResetResult(BaseModel):
    status: str = "reset"
    counts: dict[str, int]
