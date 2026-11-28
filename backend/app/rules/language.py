"""Which language is this text in? By script, because that is reliable.

Kannada, Devanagari (Hindi) and Tamil each have their own Unicode block, so a sentence
mostly in one script is that language. Latin text could be English or romanised Kannada,
Hindi or Tamil, so it says nothing; the patient's own setting is kept.
"""

SCRIPTS = {
    "kn": (0x0C80, 0x0CFF),
    "hi": (0x0900, 0x097F),
    "ta": (0x0B80, 0x0BFF),
}
SHARE = 0.6  # at least this share of the letters must be in one script


def detect_script(text: str) -> str | None:
    counts = dict.fromkeys(SCRIPTS, 0)
    letters = 0
    for ch in text:
        if not ch.isalpha() and not ("ऀ" <= ch <= "෿"):
            continue
        letters += 1
        code = ord(ch)
        for lang, (low, high) in SCRIPTS.items():
            if low <= code <= high:
                counts[lang] += 1
    if letters == 0:
        return None
    lang, top = max(counts.items(), key=lambda kv: kv[1])
    return lang if top / letters >= SHARE else None
