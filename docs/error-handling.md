# Error handling: how to trigger each case

Every row of the spec's error-handling table, how to make it happen on purpose, and what
CareVoice does. The rule behind all of them: **when unsure, ask again or escalate to the
doctor; never guess, never reassure.**

Start the app with `docker compose up --build` (no `.env` needed), open a patient link from
"I'm a patient", and use the report screen (the big mic) unless a row says otherwise.

| Situation | How to trigger it | What CareVoice does | Tested in |
| --- | --- | --- | --- |
| Background noise | Speak with a TV on, or anything the browser hears with low confidence (< 0.6) | First time: "Sorry, I couldn't hear you clearly. Please say it again, closer to the phone." in the patient's language. A second low-confidence result is sent, and the server makes it an **alert** for the doctor | `ErrorHandling.test.tsx` (low confidence), `test_error_handling.py::test_hard_to_hear_speech...` |
| Clip too short or silent | Tap the mic and say nothing, or stop within a second | Same "couldn't hear you" message; nothing is uploaded | `components.test.tsx`, `clip.test.ts` |
| Two failed attempts in a row | Fail twice as above | Big symptom buttons (pain, redness, bleeding, fever, swelling, can't see well, wound problem), **Call hospital**, and "type instead" open. Tapped symptoms make a normal report with a read-back | `ErrorHandling.test.tsx` (two failed tries), `test_error_handling.py::test_tapped_icons...` |
| Mixed languages | Say "kannu tumba red aagide, pain ide" or "aankh mein dard hai" | Accepted as it is; every language's words are matched at once; the doctor gets English | `tests/fixtures/eval/symptoms.yaml` (mixed rows) |
| Wrong language | As a Kannada patient, type or say something in Hindi script ("आँख लाल है") | The read-back is in Hindi, with "You spoke हिंदी. Use हिंदी from now on?". Or tap **Language** in the header, or say "Hindi" there. The patient's (or carer's own) preference changes and is on the timeline | `ErrorHandling.test.tsx`, `test_error_handling.py` (language tests) |
| Strong accent | Any misheard sentence | The read-back catches it (patient says no); the doctor sees the original words and recording beside the English | `test_reports_api.py` |
| Read-back is wrong | Press **No** (or say "illa" / "nahi") | "Sorry. Please tell me again what is wrong." After two "no"s the symptom buttons are offered | `ErrorHandling.test.tsx`, `Reports.test.tsx` |
| Doctor's dictation unclear | Dictate "add timolol drops" with no dose | The field turns yellow and Approve stays off until fixed | `test_discharges_api.py`, `NewDischargePage.test.tsx` |
| Symptom may be a red flag | Report anything the template can't place, or a red-flag word | Treated as a red flag: alert on the dashboard, "come to the hospital today" to the patient | `test_outcomes_api.py`, `test_rules_symptoms.py` |
| LLM bad JSON or timeout | `SIMULATE_FAILURES=llm docker compose up -d`, then report anything | Tried twice, then the rule engine answers; the doctor's report shows **Needs review** | `test_error_handling.py::test_a_failing_llm...`, `test_ai_registry.py` |
| Speech provider down or no key | `PROVIDER_MODE=real docker compose up -d` (no keys) | Browser speech is used; patients see "Running in basic voice mode"; staff see "Key not set" | `ErrorHandling.test.tsx` (basic voice), `test_error_handling.py::test_real_mode...` |
| Translation uncertain | Doctor replies with free text in demo mode, or `SIMULATE_FAILURES=translate` | The translator fails over to the verified phrasebook, then keeps the English; the doctor is told before sending | `test_error_handling.py::test_a_failing_translator...`, `test_outcomes_api.py` |
| Patient offline | Stop the server (`docker compose stop`), then report something | "No internet. Your message is saved and will be sent when you are back online." Saved in IndexedDB with the recording; sent when the network returns or the screen is opened again | `ErrorHandling.test.tsx` (offline) |
| Double tap on Send/Approve | Tap Approve, a remedy, a reply or Yes twice | Sent once; the second tap returns the first result | `test_discharges_api.py`, `test_outcomes_api.py`, `test_reports_api.py` |
| Anything unexpected | A server error | A kind message in the patient's language with **Try again**; the server never shows details or stack traces; a crashed screen shows the same instead of a blank page | `test_error_handling.py::test_an_unexpected_error...`, `ErrorHandling.test.tsx` (no network) |
