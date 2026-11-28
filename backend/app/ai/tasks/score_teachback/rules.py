from app.ai.tasks.score_teachback.schema import ScoreTeachbackInput, TeachBack
from app.rules.teachback import score_teachback


def run(data: ScoreTeachbackInput) -> TeachBack:
    return score_teachback(data)
