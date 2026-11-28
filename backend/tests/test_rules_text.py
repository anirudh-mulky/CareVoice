from pathlib import Path

import pytest

from app.rules.lexicon import get_lexicon, load_lexicon
from app.rules.text import Keyword, clauses_of, find_hits, normalise, tokens_of


def hits(keyword: str, lang: str, text: str) -> list[bool]:
    """Negated flag for each place the keyword occurs in the text."""
    lex = get_lexicon()
    clauses = clauses_of(text, lex.clause_breakers)
    return [h.negated for h in find_hits([Keyword.build(keyword, lang)], clauses, lex.negation)]


def test_normalise_handles_case_apostrophes_and_hindi_variants() -> None:
    assert normalise("  Can't   SEE ") == "cant see"
    assert normalise("ज़्यादा") == normalise("ज्यादा")
    assert normalise("हाँ") == normalise("हां")
    assert tokens_of("red-a irukku!") == ["red", "a", "irukku"]


def test_clauses_split_on_punctuation_and_contrast_words() -> None:
    lex = get_lexicon()
    assert clauses_of("no pain but red eye", lex.clause_breakers) == [
        ["no", "pain"],
        ["red", "eye"],
    ]
    assert clauses_of("novu illa, turike ide", lex.clause_breakers) == [
        ["novu", "illa"],
        ["turike", "ide"],
    ]


@pytest.mark.parametrize(
    ("keyword", "lang", "text"),
    [
        ("kempu", "kn", "kannu kempagide"),  # romanised stem
        ("ಕೆಂಪು", "kn", "ಕಣ್ಣು ಕೆಂಪಾಗಿದೆ"),  # native-script stem
        ("வலி", "ta", "வலிக்குது"),
        ("vali", "ta", "valikkuthu"),
        ("pain", "en", "it is painful"),  # English ending
        ("can't see", "en", "I cannot... I can't see"),
        ("pet mein dard", "hi", "pet mein bahut... pet mein dard hai"),
    ],
)
def test_keywords_match_inflected_forms(keyword: str, lang: str, text: str) -> None:
    assert hits(keyword, lang, text)


@pytest.mark.parametrize(
    ("keyword", "lang", "text"),
    [
        ("red", "en", "please reduce the dose"),  # English is whole-word, not prefix
        ("vali", "ta", "valathu kann"),  # "right eye" must not read as pain
        ("pain", "en", "spain"),
    ],
)
def test_keywords_do_not_overmatch(keyword: str, lang: str, text: str) -> None:
    assert not hits(keyword, lang, text)


@pytest.mark.parametrize(
    ("keyword", "lang", "text", "negated"),
    [
        ("novu", "kn", "novu illa", True),
        ("ನೋವು", "kn", "ನೋವು ಇಲ್ಲ", True),
        ("dard", "hi", "dard nahi hai", True),
        ("dard", "hi", "koi dard nahi", True),
        ("vali", "ta", "vali illa", True),
        ("vali", "ta", "valikkala", True),  # negation fused onto the word
        ("pain", "en", "no pain", True),
        ("fever", "en", "I don't have fever", True),
        # Not negations: these must still escalate.
        ("dard", "hi", "dard kam nahi ho raha", False),
        ("novu", "kn", "novu kadime aagilla", False),
        ("pain", "en", "not much pain", False),
        ("bleeding", "en", "I can't stop the bleeding", False),
        ("pain", "en", "the pain is not going away", False),
        ("theriyala", "ta", "kan theriyala", False),  # the keyword itself is negative
    ],
)
def test_negation(keyword: str, lang: str, text: str, negated: bool) -> None:
    assert hits(keyword, lang, text) == [negated]


def test_negation_does_not_cross_clauses() -> None:
    assert hits("turike", "kn", "novu illa, turike ide") == [False]
    assert hits("pain", "en", "no fever but pain") == [False]


def test_lexicon_loads_every_language_and_concept() -> None:
    lex = get_lexicon()
    assert set(lex.languages) == {"en", "kn", "hi", "ta"}
    for concept in lex.concepts.values():
        assert {k.language for k in concept.keywords} == {"en", "kn", "hi", "ta"}, concept.id
        assert set(concept.labels) == {"en", "kn", "hi", "ta"}, concept.id
    assert lex.language_names()["ಕನ್ನಡ"] == "kn"
    assert lex.pack("kn-IN").code == "kn"
    assert lex.pack("xx").code == "en"


def test_unquoted_yaml_booleans_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "en.yaml").write_text("language: en\nyes: [yes, yeah]\n")
    with pytest.raises(ValueError, match="quote"):
        load_lexicon(tmp_path)
