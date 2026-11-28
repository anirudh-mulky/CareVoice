from pydantic import BaseModel


class ResetResult(BaseModel):
    status: str = "reset"
    counts: dict[str, int]


class AdvancedPatient(BaseModel):
    patient_name: str
    recovery_day: int
    reminders_sent: int


class AdvanceResult(BaseModel):
    patients: list[AdvancedPatient]
    reminders_sent: int
