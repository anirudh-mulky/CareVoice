import pytest

from app.rules.language import detect_script


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ಕಣ್ಣು ತುಂಬಾ ಕೆಂಪಾಗಿದೆ", "kn"),
        ("आँख बहुत लाल है", "hi"),
        ("கண் ரொம்ப சிவப்பா இருக்கு", "ta"),
        ("आँख में dard है", "hi"),  # mixed, mostly Devanagari
        ("Kannu tumba kempagide", None),  # romanised: could be anything
        ("my eye is red", None),
        ("", None),
        ("123 !!", None),
    ],
)
def test_detect_script(text: str, expected: str | None) -> None:
    assert detect_script(text) == expected
