"""Rule-based teach-back scorer: which red flags did the patient mention in their own words?

Mentions count even inside a conditional or negative ("come back if I can't see"), since
the question asks the patient to name the warning signs.
"""

from fractions import Fraction

from app.ai.tasks.score_teachback.schema import ScoreTeachbackInput, TeachBack
from app.rules.lexicon import Lexicon, get_lexicon
from app.rules.text import clauses_of, find_hits


def passes(mentioned: int, total: int, threshold: float) -> bool:
    """Exact comparison, so 3 of 4 flags passes a 0.75 threshold (no float rounding)."""
    if total == 0:
        return True
    return Fraction(mentioned, total) >= Fraction(str(threshold))


def score_teachback(data: ScoreTeachbackInput, lexicon: Lexicon | None = None) -> TeachBack:
    lex = lexicon or get_lexicon()
    text = " . ".join(t for t in (data.answer_native, data.answer_en) if t)
    clauses = clauses_of(text, lex.clause_breakers)
    mentioned, missed = [], []
    for flag in data.red_flags:
        keywords = lex.keywords_for(flag.keywords, flag.concepts)
        if find_hits(keywords, clauses, lex.negation):
            mentioned.append(flag.id)
        else:
            missed.append(flag.id)
    return TeachBack(
        mentioned_flag_ids=mentioned,
        missed_flag_ids=missed,
        passed=passes(len(mentioned), len(data.red_flags), data.pass_threshold),
    )
