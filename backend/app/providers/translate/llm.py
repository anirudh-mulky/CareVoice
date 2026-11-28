"""Translation through the configured LLM (TRANSLATE_PROVIDER=llm).

Used for the short live texts (the doctor's extra instructions and replies); template
content always comes from the doctor-verified translations instead.
"""

from pydantic import BaseModel

from app.providers.base import LLM

LANGUAGE_NAMES = {"en": "English", "kn": "Kannada", "hi": "Hindi", "ta": "Tamil"}
PROMPT = """You translate short messages from a hospital care team to a patient.
Translate the TEXT from {src} to {dst}. Keep the meaning exactly: do not add, remove or
soften anything, and do not give advice. Keep medicine names, doses and numbers as they are.
Use simple, everyday words a patient would say. If a word has no safe translation, keep it
in English. Return only the translation.

TEXT:
{text}"""


class Translation(BaseModel):
    translated_text: str


class LLMTranslator:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        self.name = f"llm:{llm.name}"

    async def translate(self, text: str, src: str, dst: str) -> str:
        src_base, dst_base = src.split("-")[0], dst.split("-")[0]
        if src_base == dst_base or not text.strip():
            return text
        prompt = PROMPT.format(
            src=LANGUAGE_NAMES.get(src_base, src_base),
            dst=LANGUAGE_NAMES.get(dst_base, dst_base),
            text=text.strip(),
        )
        result = await self.llm.json("translate", prompt, Translation)
        return result.translated_text.strip() or text
