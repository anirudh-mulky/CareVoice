from app.ai.tasks.extract_discharge.schema import Discharge, ExtractDischargeInput
from app.rules.extractors import extract_discharge


def run(data: ExtractDischargeInput) -> Discharge:
    return extract_discharge(data)
