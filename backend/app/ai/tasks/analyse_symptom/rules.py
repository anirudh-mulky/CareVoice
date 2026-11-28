from app.ai.tasks.analyse_symptom.schema import AnalyseSymptomInput, Symptom
from app.rules.symptoms import analyse_symptom


def run(data: AnalyseSymptomInput) -> Symptom:
    return analyse_symptom(data)
