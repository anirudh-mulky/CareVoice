import pytest

from app.rules.yes_no import yes_or_no


@pytest.mark.parametrize(
    ("text", "lang", "expected"),
    [
        ("haudu", "kn", True),
        ("ಹೌದು, ಸರಿ", "kn", True),
        ("illa", "kn", False),
        ("ತಪ್ಪು", "kn", False),
        ("sari illa", "kn", None),  # "not right": unclear, tap a button
        ("हाँ जी", "hi", True),
        ("nahi galat hai", "hi", False),
        ("aamaa", "ta", True),
        ("இல்லை", "ta", False),
        ("yes", "kn", True),  # English always accepted
        ("not right", "en", False),
        ("hmm", "kn", None),
        ("", "kn", None),
    ],
)
def test_spoken_yes_or_no(text: str, lang: str, expected: bool | None) -> None:
    assert yes_or_no(text, lang) is expected
