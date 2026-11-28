# CareVoice

**The doctor speaks once. The patient understands. Both have a record.**

Patients leave hospital with care instructions given once, verbally, often in English, and many
cannot read the printed sheet (after eye surgery, nobody can). CareVoice lets the doctor discharge a
patient by speaking one sentence. The patient and their carer hear the instructions in their own
language, prove they understood by answering a spoken question, and report problems by talking.
The doctor reads each report in English, with red flags first.

Built for the Scaler x Wispr hackathon, Round 2, in the Healthcare access theme.

- **Demo video:** _link to add_
- **Live link:** _none_
- **Pitch deck:** _link to add_

## Quick start

You need only Docker (Docker Desktop, or Docker Engine with Compose v2.24 or newer). You do not need
a `.env` file or any API keys.

```bash
git clone https://github.com/anirudh-mulky/CareVoice.git
cd CareVoice
docker compose up --build
```

Open **http://localhost:3000** in Chrome. The first build takes a few minutes. The app is ready
when the log says `CareVoice ready on :3000 (demo mode)`.

The database is created and filled with three synthetic demo patients on first start. No real patient
data is used anywhere. The other useful addresses are:

- Health check: http://localhost:3000/api/v1/health
- API docs: http://localhost:3000/api/docs
- Provider status: http://localhost:3000/api/v1/system/status

To stop the app, press `Ctrl+C`. To start again from fresh demo data, use **Reset demo** in the
header, or run `docker compose down -v`.

## Try the core flow (about 5 minutes)

Use two browser windows side by side: one for the doctor and one for the patient. Every voice step
also has a **Type instead** box, so the flow works without a microphone.

1. **Doctor dictates a discharge.** Click **I'm a doctor**, then **New discharge**. Tap the mic and
   say (or type): _"Ramesh, 68, cataract right eye, standard template, diabetic so check sugar daily,
   add timolol drops, language Kannada."_ The care card fills itself in. The timolol line has no
   dose, so it is highlighted in yellow and **Approve** stays disabled. Doses are never guessed. Add
   the dose (or remove the line), then approve the card.
2. **Patient hears it in Kannada.** Open the patient link shown after approval. You can also go to
   the main screen, click **I'm a patient** and pick Ramesh. The card is in Kannada, with warning
   signs first. Tap play to hear it read aloud. The carer's link shows the same card.
3. **Spoken teach-back.** The app asks when to come back to hospital. If the answer names only some
   of the warning signs, the app explains the missed ones again. After two tries the patient is
   marked **Understood** or **Needs follow-up** on the doctor's dashboard.
4. **Next day.** Click **Simulate next day** (on the doctor dashboard or the patient picker). That
   day's reminder arrives in the chat.
5. **Red flag.** On Ramesh's home screen, tap the big mic and say _"Kannu tumba kempagide, novu
   ide."_ ("My eye is very red and it hurts."). The app reads it back in Kannada; answer **yes**. The
   doctor's dashboard shows a red **Alert** with the Kannada transcript beside the English
   translation. The patient is told straight away to visit the hospital today.
6. **Minor symptom in Hindi.** As Sunita, say _"Tanko ke paas bahut khujli ho rahi hai, aur kuch
   nahi."_ ("A lot of itching near the stitches, nothing else."). The doctor sees the remedy from
   Sunita's own template and approves it, and Sunita receives it in Hindi.
7. **When speech fails.** If a recording is too short or silent, the app asks the patient to say it
   again. After two failed tries, large symptom buttons and **Call hospital** appear.
8. **Record.** The doctor's patient page shows a time-stamped timeline of everything that was sent
   and confirmed.

How to trigger every error case on purpose is in [docs/error-handling.md](docs/error-handling.md).

## Safety rules built into the app

- **CareVoice never diagnoses or gives medical advice.** Remedies come only from the doctor's own
  template, and the doctor approves them before they are sent.
- **When unsure, it escalates.** Anything that might be a red flag goes to the doctor as an alert.
  Low speech-recognition confidence also counts as an alert. The patient is told to visit the
  hospital that day.
- **Nothing reaches a patient without the doctor's approval.** The one exception is the automatic
  safety message sent with an alert.
- **Every patient screen** shows a **Call hospital** button and the message "This app does not replace
  your doctor. In an emergency, go to the nearest hospital", in the patient's language.

## Demo mode and real mode

| | Demo mode (default) | Real mode |
|---|---|---|
| Keys needed | None | Your own Sarvam AI and/or Anthropic keys |
| Speech to text | Browser Web Speech API (Chrome) | Sarvam AI, on the server |
| Spoken voice | Browser speech synthesis | Sarvam AI, stored as audio |
| Translation | Pre-translated templates and demo phrases | Sarvam AI, or the LLM |
| Understanding dictation and reports | Rule engine with Kannada, Hindi, Tamil and English word lists | Claude, with the rule engine as fallback |

Demo mode starts with no setup. To use real mode:

1. `cp .env.example .env`. Git ignores `.env`; never commit it.
2. Set `PROVIDER_MODE=real`. Set `STT_PROVIDER`, `TTS_PROVIDER` and `TRANSLATE_PROVIDER` to
   `sarvam` and fill in `SARVAM_API_KEY`. Set `LLM_PROVIDER=anthropic` and fill in `LLM_API_KEY`.
3. Run `docker compose up -d --build`. Then check http://localhost:3000/api/v1/system/status: each
   provider should report `"mode": "real"`.

Any provider whose key is missing falls back to demo mode. The staff screens then show a **Key not
set, using demo mode** badge; nothing crashes. If a real provider fails during use, the app also
falls back: to browser speech, and to the rule engine for understanding. `.env.example` lists every
setting with its default.

## Architecture

One Docker container serves both the React app and the FastAPI backend on port 3000.

```
Doctor screens (React)      Patient and carer screens (React, mobile)
              \                     /
               FastAPI  /api/v1  (one container, port 3000)
               ├── modules/      one folder per feature; modules talk only through events
               ├── core/events   in-process event bus; every event is also saved to the events table
               ├── providers/    speech, voice, translation, LLM: each has a demo and a real version
               ├── channels/     in-app chat now; WhatsApp and SMS later
               ├── ai/tasks/     extract_template, extract_discharge, score_teachback, analyse_symptom
               └── rules/        keyword lexicons per language (data, not code) and the rule engine
              SQLite in demo (Postgres via DATABASE_URL), audio in ./data/media
```

| Module | What it does | Listens to |
|---|---|---|
| templates | Doctor's care templates, versioned | |
| discharges | Dictation to a care card, with an approval gate | |
| delivery | Sends the care card to the patient and carer, and creates their private links | `discharge.approved` |
| teachback | Asks the spoken question, scores the answer, explains missed signs again | `message.sent` |
| reports | Spoken symptom, read-back, yes or no, English report | |
| outcomes | Alert with safety message; template remedy; doctor reply; close episode | `report.confirmed` |
| reminders | Timed reminders from the template, and Simulate next day | `discharge.approved`, `demo.day_advanced`, `episode.closed` |
| timeline | Read-only time-stamped record for each patient | every event |
| voice | Server-side speech in real mode | |
| demo | Seed data, Reset demo, Simulate next day | |

A new feature, such as SMS alerts, is a new module that listens to events; existing modules do not
change. The full design is in [docs/spec.md](docs/spec.md).

**Stack:** FastAPI, Pydantic v2, SQLAlchemy 2 (Python 3.11). React 19, TypeScript, Vite, Tailwind,
shadcn/ui, TanStack Query. Frontend API types are generated from the backend's OpenAPI schema.

## Develop

```bash
make install   # backend venv and frontend packages
make dev       # API on :8000 and Vite on :5173 with hot reload (Vite proxies /api)
make test      # pytest and vitest
make lint      # ruff, mypy, eslint, tsc
make types     # regenerate frontend API types after an API change (CI fails if they drift)
make reset     # restore the demo data in the local database
```

CI runs the lint, type checks, tests, a secret scan (gitleaks) and a Docker build on every push.

## Team

Team Sicarios: _names and roles to add_

## Licence

[MIT](LICENSE)
