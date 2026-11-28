"""Demo TTS: the patient's browser speaks the text with speechSynthesis.

Returning no audio tells the client to speak the message itself, so nothing is
generated or stored on the server in demo mode.
"""


class DemoTTS:
    name = "demo"
    client_side = True

    async def speak(self, text: str, lang: str) -> bytes:
        return b""
