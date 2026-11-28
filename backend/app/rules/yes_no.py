"""Spoken yes/no for read-back confirmation ("haudu", "nahi", "sari", "wrong").

Words come from each lexicon's "yes" and "no" lists; the patient's language and English
are both accepted. If both kinds appear ("sari illa" = not right) or neither does, the
answer is unclear and the patient is asked to tap a button: never guess a yes.
"""

from app.rules.lexicon import Lexicon, get_lexicon
from app.rules.text import normalise, tokens_of


def _found(text: str, words: set[str]) -> bool:
    tokens = tokens_of(text)
    joined = f" {' '.join(tokens)} "
    return any((f" {w} " in joined) if " " in w else (w in tokens) for w in words)


def yes_or_no(text: str, lang: str, lexicon: Lexicon | None = None) -> bool | None:
    lex = lexicon or get_lexicon()
    packs = [lex.pack(lang), lex.pack("en")]
    yes = packs[0].words("yes") | packs[1].words("yes")
    no = packs[0].words("no") | packs[1].words("no")
    if not normalise(text):
        return None
    # A multi-word "no" ("not right") must not also count its "right" as a yes.
    rest = f" {' '.join(tokens_of(text))} "
    phrases = sorted((w for w in no if " " in w), key=len, reverse=True)
    for phrase in phrases:
        rest = rest.replace(f" {phrase} ", " ")
    said_yes, said_no = _found(rest, yes), _found(text, no)
    if said_yes == said_no:
        return None
    return said_yes
