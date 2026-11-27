# CareVoice — Round 2 Build Spec

Nov 27, 2026 · @ani

## How to build from this doc

Build CareVoice in 14 small parts, each one built, tested and pushed before the next starts, so the app always runs. This doc is the single source of truth and lives in the repo as docs/spec.md.

- Work on one part at a time from "Build parts", staying inside the files and modules that part lists.
- When a part is done: run its tests, run `docker compose up --build` and confirm the app still opens on http://localhost:3000, and note what changed and what to test by hand. Do not start the next part.
- Test by hand using the part's "Done when" list. If it passes, commit with the part's commit message and push. If not, fix what failed before moving on.
- A new idea while testing? Add it to "User stories and features" with a priority and a part, then build it as its own module (see "Modular design rules"), never by patching a finished part.

## Round 2 brief and deliverables

We are building one voice-first core flow that works end to end in the Healthcare access theme, extending our Round 1 idea, and submitting it once by **30 Nov, 11:59 pm IST**. CareVoice is the product; for Round 2 we prove its heart: a doctor speaks instructions, a patient hears them in their language, and a patient's spoken symptom comes back to the doctor as an English report.

**What the brief asks for**

- The main task is done by speaking. Take something people do today by typing, tapping or filling forms and make it work by voice.
- One core flow that works end to end. Not a full product.
- One theme and a real problem within it. We pick **Healthcare access** and extend our Round 1 idea.

**What we submit (one submission per team, only once)**

|  |  |  |  |
| --- | --- | --- | --- |
| # | Deliverable | Official rule | Implication for us |
| 1 | Code on GitHub | Public repo. A docker-compose.yml that starts the app with one command, on a port (e.g. 3000:3000) that shows **our app, not a default server page**. Starts and shows its main screen with **no secret keys** and **no .env file**; .env.example with placeholders. About **300+ lines of our own code** written during the hackathon; a lightly edited starter template fails. If it doesn't start, the build can't move ahead | One container serving both the React build and the API on port 3000; every setting has a safe default; database auto-created and seeded on first start; features needing keys show "key not set" and fall back to demo mode |
| 2 | Demo video on YouTube | Public or unlisted, 3 minutes or less, product working | Script it around the core flow; real voices, real app |
| 3 | Pitch deck (PDF) | Judges read the **words, not the pictures**: key points as text. Must cover (1) problem and solution, (2) who it's for and how many users there could be, (3) what it depends on and what happens if those services get costly or stop working, (4) launch plan: first users and growth | Every slide carries its point in sentences; diagrams and screenshots are extras, never the only place a point is made |
| 4 | Live link | Optional; small bonus if it works; never counts against us; self-hosted | Deploy the same Docker image in demo mode, only if time allows |

**Prototype, not the full product:** the full version is built at the finale, so Round 2 is judged on one flow that starts reliably and works. **Tip from the organisers:** have a friend download the repo and start it before we submit.

**What the judges are likely to reward:** voice doing the real work (not a mic bolted onto a form), a flow that genuinely works on camera, handling of Indian languages, accents and noise, and a credible path from prototype to real hospitals.

**Hard requirement to protect at all costs:** git clone → docker compose up → open http://localhost:3000 → CareVoice's main screen, with no keys and no .env. If this fails, nothing else we build is seen.

## Problem, users and why voice

Patients leave hospital with critical care instructions given once, verbally, in English, at the worst moment, and doctors have no record of what was said. CareVoice replaces the rushed discharge talk and the unreadable printed sheet with spoken instructions in the patient's language, and replaces "wait till the next visit" with a voice note the doctor reads in English.

**Today's process (what voice replaces)**

- Doctor repeats the same discharge speech for every C-section, cataract or fracture.
- Patient gets a printed sheet, often in English, that many can't read; a cataract patient with a covered eye can't read at all.
- The carer who will actually look after the patient often wasn't in the room.
- Worried at home, the patient either ignores a symptom or travels back to ask. Complications are caught late.
- Families later say "we were never told"; there is no record.

**Users**

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| User | Who | Device | Speaks | What they need |
| Doctor | Busy, sees many patients a day | Desktop or laptop in clinic | English with medical terms, varied regional accents | Discharge in under a minute, no repeating, a record |
| Nurse / front desk | Often does the actual discharge | Desktop | English and a local language | A simple approve-and-send step |
| Patient | Often elderly, low literacy, may have had eye surgery | Low-to-mid Android phone, WhatsApp | Any Indian language, code-mixed ("wound se paani aa raha hai") | Hear instructions, be reminded, report a problem by talking |
| Carer | Son, daughter or spouse | Own phone | Any Indian language | Same messages as the patient |
| Hospital admin | The buyer | Desktop | English | Fewer complications coming back, fewer disputes, data |

**Why voice is the main way in, not a feature:** doctors have seconds, not time to type; many patients and carers cannot read an English sheet; eye patients cannot read at all; teach-back only works spoken; and people describe symptoms naturally by talking in mixed languages. Screens and dashboards still exist for doctors and for anyone who wants to read their history.

## Scope: the one core flow, and what waits

The Round 2 build is one loop: **doctor speaks instructions → patient hears them in their language and proves they understood → patient speaks a symptom → doctor gets an English report and responds → patient hears the reply.** Everything else is designed for, but not built, so the architecture scales without slowing the 3-day build.

**P0 — must work on camera (the core flow)**

- Doctor dictates a discharge by voice; the app extracts a structured care card; doctor edits and approves.
- Card is translated into the patient's language and delivered as text + voice note in a WhatsApp-style chat.
- Spoken teach-back: app asks about red flags, patient answers by voice, app scores it, re-explains missed flags, sets status.
- Patient taps the big mic, describes a symptom in Kannada/Hindi/Tamil; app reads back a summary for confirmation.
- Doctor receives a detailed English report (original audio, native transcript beside translation, symptoms, recovery day, medicines).
- Red flag → red Alert on the dashboard + safety message to patient. Minor symptom → remedy from the doctor's template, doctor approves, patient receives it translated.
- Runs with **no secret keys** (demo mode) and with real providers when keys are set.

**P1 — build if P0 is solid by Day 2 evening**

- Voice-created templates (otherwise seed two templates: cataract, C-section).
- Timed reminders with a "Simulate next day" button.
- Doctor voice reply translated to the patient.
- Read-only event timeline per patient.
- Deployed live link.

**P2 — designed in this doc, not built for Round 2**

- Real WhatsApp Business API delivery and inbound voice notes.
- Native Android home-screen widget.
- Login, roles, multi-hospital tenancy, HIS/EMR integration (ABDM).
- Analytics dashboards, billing, audit exports.

**Out of scope, always:** diagnosis, triage scores, or any medical advice not written by the doctor.

## User stories and features

Every feature traces back to a person and a need; the part column says where it gets built. P0 = core flow (must ship), P1 = build if time, P2 = after Round 2. Add new stories here first, then build them as a module.

|  |  |  |  |
| --- | --- | --- | --- |
| User | As this user, I want to… | Priority | Part |
| Patient | hear my care instructions in my own language, red flags first | P0 | 6 |
| Patient | replay any voice note as many times as I need | P0 | 6 |
| Patient | see a "Call hospital" button on every screen | P0 | 6 |
| Patient | prove I understood by answering a spoken question | P0 | 7 |
| Patient | report a problem by talking, in my language, mixed with English | P0 | 8 |
| Patient | hear what the app understood and say yes or no | P0 | 8 |
| Patient | type or tap symptom icons if speaking doesn't work | P0 | 11 |
| Patient | hear my doctor's reply and any remedy in my language | P0 | 9 |
| Patient | switch my language if the app picked the wrong one | P1 | 11 |
| Patient | see today's medicines and reminder on my home screen | P1 | 10 |
| Patient | see my past reports and replies | P1 | 9 |
| Patient | read large, high-contrast text | P1 | 13 |
| Carer | receive everything the patient receives | P0 | 6 |
| Carer | report on the patient's behalf, marked as reported by carer | P1 | 8 |
| Doctor | discharge a patient by speaking one sentence | P0 | 5 |
| Doctor | see unclear doses, drugs or dates highlighted and fix them before sending | P0 | 5 |
| Doctor | see alerts first on my dashboard | P0 | 8 |
| Doctor | read an English report with the original audio and native transcript side by side | P0 | 8 |
| Doctor | approve or edit a suggested remedy, taken only from my template | P0 | 9 |
| Doctor | reply to a patient by voice or text | P1 | 9 |
| Doctor | mark an alert handled and close a patient's care episode | P1 | 9 |
| Doctor | search and filter patients by status | P1 | 8 |
| Doctor | create or edit a template by speaking | P1 | 5 |
| Doctor | see the full time-stamped timeline for a patient | P1 | 10 |
| Nurse | send a discharge the doctor prepared, and see alerts | P2 | later |
| Hospital admin | manage templates, staff and see usage metrics | P2 | later |
| Demo / judges | reset demo data with one button, and simulate the next day | P1 | 10, 13 |

## End-to-end user flow

The core flow passes between three people and the system eleven times, and ends in one of three outcomes depending on what the patient said. Every arrow is a voice interaction or a screen the demo must show.

*(Diagram in the original doc: core flow · 3 lanes, 11 steps, 3 outcomes)*

Anything that might be a red flag, or that the system is unsure about, goes to the red Alert branch; only a confident minor match gets a template remedy, and the doctor still approves it. Every step is also written to the patient's time-stamped timeline.

## System architecture

Two React front ends talk to one stateless FastAPI service; slow speech and LLM work runs as jobs, and every external provider sits behind an adapter that has a keyless demo version. Dashed parts are designed now but switched on only in production.

*(Diagram in the original doc: system architecture · dashed = production only)*

In demo mode, speech runs in the patient's browser (Web Speech API and speechSynthesis) and a rule engine replaces the LLM, so the whole system starts with no keys; setting PROVIDER\_MODE=real plus keys routes the same calls to the external providers.

## Modular design rules

Each feature lives in its own module that registers itself, talks to others through events, and can be switched off by config, so adding something during testing means adding a module, not editing five files. Every part must follow these rules.

- **Feature modules (backend):** app/modules/<feature>/ holds router.py, service.py, schemas.py, models.py and tests/. Modules: templates, discharges, delivery, teachback, reports, outcomes, reminders, timeline, demo. A module never imports another module's service or models directly.
- **Self-registration:** each module exposes register(app, bus). main.py loops over ENABLED\_MODULES from config (default: all) and calls it. Turning a feature off = removing it from that list.
- **Event bus between modules:** services publish domain events and other modules subscribe. Events: discharge.approved, message.sent, teachback.scored, report.confirmed, report.alert, remedy.approved, doctor.replied, reminder.due. Example: delivery listens to discharge.approved; timeline listens to everything. A new feature (SMS alerts, analytics) = a new listener, no change to existing code. Round 2 uses an in-process bus; production swaps in Redis with the same interface.
- **Providers by name:** app/providers/ has interfaces (STT, TTS, Translator, LLM) and a registry that picks implementations from config (demo, sarvam, bhashini, openai, ...). A provider missing its key reports key\_not\_set and the registry falls back to demo.
- **Delivery channels by name:** app/channels/ has a Channel interface (send(message)) with in\_app now and whatsapp, sms, ivr later. delivery sends to every channel enabled for the patient.
- **AI tasks as plug-ins:** app/ai/tasks/<task>/ holds schema.py, prompt.md and rules.py (the demo fallback). A registry maps task names to them. A new AI feature = a new task folder.
- **Data, not code, for content:** templates, red flags, keyword lexicons (app/rules/lexicons/<lang>.yaml) and UI strings (frontend/src/i18n/<lang>.json) are data. Adding a language = adding files, no code changes.
- **Feature folders (frontend):** src/features/<feature>/ holds pages, components and API hooks; each exports its routes, and src/app/routes.ts collects them. Shared pieces (mic, audio player, layout) live in src/shared/.
- **Typed contract:** generate TypeScript types from FastAPI's OpenAPI schema (openapi-typescript) so frontend and backend never drift.
- **Every module ships with tests**, and every state change writes an event, so the timeline and audit log work for features nobody has thought of yet.

## Tech stack and services

We use React + FastAPI + Postgres, with every external AI service behind a provider interface that has a free, keyless **demo** implementation. That one decision satisfies the "starts without secret keys" rule and keeps the path to production open.

|  |  |  |  |
| --- | --- | --- | --- |
| Layer | Round 2 choice | Why | Production path |
| Frontend | React + Vite + TypeScript + Tailwind + shadcn/ui, React Router, TanStack Query | Fast to build, team already knows React | Same; add PWA install + push |
| Backend API | FastAPI (Python 3.11), Pydantic v2, SQLAlchemy 2 + Alembic | Python is best for AI/audio work; Pydantic gives strict schemas for LLM output | Same, containerised, horizontally scaled |
| Database | SQLite by default (zero config), Postgres via DATABASE\_URL | Clone-and-run with no setup | Managed Postgres (India region), read replicas later |
| Audio storage | Local ./media folder | No keys | S3-compatible bucket (S3 Mumbai / R2), signed URLs |
| Background jobs | FastAPI BackgroundTasks + APScheduler for reminders | Simple, in-process | Redis + worker queue (arq or Celery), separate scheduler |
| Speech-to-text | Demo: browser Web Speech API (hi-IN, kn-IN, ta-IN, en-IN). Real: Indian-language STT provider | Works in Chrome with no key | Sarvam AI or Bhashini, with auto language detection |
| Text-to-speech | Demo: browser speechSynthesis. Real: Indian-language TTS provider, MP3 stored | No key | Same provider, cached audio per message |
| LLM (extraction, scoring, report) | Demo: rule-based extractor + multilingual keyword matcher. Real: any LLM via one adapter | Deterministic offline demo; real LLM when a key exists | Claude / Gemini / OpenAI behind the adapter; eval set before switching models |
| Translation | Demo: pre-translated seed templates + LLM-free fallback. Real: provider or LLM translation | Template text is translated once and cached | Doctor-verified translations per template and language |
| Messaging | In-app WhatsApp-style chat | WhatsApp API needs business verification and keys | WhatsApp Business Cloud API (templates, inbound voice notes), SMS fallback |
| Deploy | Same Docker image on a free HTTPS host (Render, Railway or Fly), demo mode on | Free tiers, live link bonus | Docker on AWS Mumbai (ECS/Fargate) or similar |
| Quality | Ruff, mypy, pytest, ESLint, Vitest, Playwright smoke test, GitHub Actions CI | Catch breakage before demo day | Same + load tests |

Check before wiring: confirm the current Sarvam AI / Bhashini endpoints, supported languages and pricing in their docs; and test browser speech in Chrome on Android, since kn-IN and ta-IN support varies by device.

## Data model

Eleven tables cover the product; every one carries hospital\_id from day one so multi-hospital tenancy needs no migration later. All ids are UUIDs, all times UTC, and events is append-only.

|  |  |  |
| --- | --- | --- |
| Table | Key columns | Notes |
| hospitals | id, name, city, default\_languages[] | Tenant root |
| users | id, hospital\_id, name, role (doctor, nurse, admin), phone, email | Staff only; patients are not users in Round 2 |
| patients | id, hospital\_id, name, age, sex, phone, preferred\_language, consent\_at, consent\_version | Consent captured at discharge |
| carers | id, patient\_id, name, relation, phone, preferred\_language | Receive everything the patient receives |
| templates | id, hospital\_id, doctor\_id, name, condition, medicines (jsonb), dos[], donts[], red\_flags (jsonb [{id, label\_en, keywords{lang:[...]}}]), minor\_symptoms (jsonb [{id, symptom\_en, remedy\_en, keywords}]), reminders (jsonb [{day, time, message\_en}]), follow\_up\_day, version | Versioned; a discharge pins the version used |
| template\_translations | template\_id, version, language, content (jsonb), verified\_by, verified\_at | Doctor or native speaker verifies once |
| discharges | id, patient\_id, doctor\_id, template\_id, template\_version, extra\_instructions[], discharged\_on, status (draft, sent, understood, needs\_followup, alert, closed), approved\_at | One per episode of care |
| messages | id, discharge\_id, direction (to\_patient, to\_doctor), kind (instructions, reminder, teachback\_q, teachback\_a, report, remedy, doctor\_reply), text\_native, text\_en, language, audio\_url, played\_at, created\_at | The chat |
| reports | id, discharge\_id, audio\_url, transcript\_native, detected\_language, stt\_confidence, translation\_en, report\_json (jsonb), matched\_flag\_ids[], matched\_minor\_ids[], suggested\_remedies (jsonb), type (alert, minor, general), status (new, seen, remedy\_sent, replied), confirmed\_by\_patient | The doctor's English report |
| events | id, hospital\_id, discharge\_id, actor\_type, actor\_id, type, payload (jsonb), created\_at | Append-only audit timeline; no updates or deletes |
| scheduled\_jobs | id, discharge\_id, kind, due\_at, status, attempts | Reminders and retries |

**Indexes:** discharges(hospital\_id, status), reports(status, created\_at), messages(discharge\_id, created\_at), events(discharge\_id, created\_at), scheduled\_jobs(status, due\_at).

**Seed data (make seed):** one hospital; Dr. Priya; templates for cataract surgery and C-section with 4–6 red flags, 2–3 minor symptoms each and keywords in Kannada, Hindi, Tamil and English; patients Ramesh (68, Kannada, cataract), Sunita (29, Hindi, C-section), Murugan (55, Tamil, cataract); one open alert and one minor report awaiting remedy approval.

## Voice and AI pipeline

Every voice interaction runs the same five stages, and each stage is a swappable provider with a keyless demo version: **capture → transcribe → understand → confirm → speak back.** The LLM only ever extracts, translates, compares and summarises against the doctor's own template; it never generates medical advice.

**Stages**

- **Capture:** MediaRecorder (webm/opus, mono, 16 kHz target, max 60 s), browser noise suppression and echo cancellation on via getUserMedia constraints. Reject clips under 1 s or with near-zero RMS energy before upload.
- **Transcribe (STT):** returns {text, language, confidence}. Demo: Web Speech API in the browser with the patient's language code. Real: server-side Indian-language STT with auto language detection.
- **Understand (LLM or rules):** one of four tasks below, each returning strict JSON validated by Pydantic; invalid JSON retries once, then falls back to the rule engine.
- **Confirm:** before any action, the patient hears a read-back in their language and answers yes/no (voice or button); the doctor sees transcript + extracted fields and edits before Approve.
- **Speak back (TTS):** text in the patient's language → audio. Demo: speechSynthesis. Real: provider MP3, cached per message.

**Provider interfaces (backend app/providers/)**

```python
class STTProvider(Protocol):
    async def transcribe(self, audio: bytes, lang_hint: str | None) -> Transcript: ...
class TTSProvider(Protocol):
    async def speak(self, text: str, lang: str) -> bytes: ...
class Translator(Protocol):
    async def translate(self, text: str, src: str, dst: str) -> str: ...
class LLM(Protocol):
    async def json(self, task: str, prompt: str, schema: type[BaseModel]) -> BaseModel: ...
```

PROVIDER\_MODE=demo|real picks implementations at startup; real also needs the matching keys, otherwise the app logs a warning and stays in demo.

**The four AI tasks and their schemas**

|  |  |  |
| --- | --- | --- |
| Task | Input | Output (Pydantic model) |
| extract\_template | Doctor's dictated template | Template{name, medicines[{name, dose, frequency, duration\_days}], dos[], donts[], red\_flags[{id, label\_en}], minor\_symptoms[{id, symptom\_en, remedy\_en}], reminders[{day, time, message\_en}], follow\_up\_day, unclear\_fields[]} |
| extract\_discharge | Doctor's discharge sentence + template list | Discharge{patient\_name, age, template\_name, side, extra\_instructions[], language, carer\_phone, unclear\_fields[]} |
| score\_teachback | Patient answer (native + English) + red flags | TeachBack{mentioned\_flag\_ids[], missed\_flag\_ids[], passed}; pass = at least 75% of flags |
| analyse\_symptom | Patient report (native + English) + this patient's template + recovery day | Symptom{summary\_en, read\_back\_native, symptoms[{name\_en, body\_part, severity\_words, onset, duration}], matched\_flag\_ids[], matched\_minor\_ids[], suggested\_remedies[{minor\_id, remedy\_en}], confidence} |

**System prompt (shared by all tasks)**

You extract structured data for a hospital post-discharge tool. Output only JSON matching the schema. Use only information the doctor or patient actually said, and the patient's own template. Never invent medicines, doses, dates, red flags or remedies. Put anything unclear in unclear\_fields. Never diagnose, reassure or give medical advice. When a symptom might match a red flag, include it and set confidence to low.

**Decision rules applied in code, not by the LLM**

- Any red-flag match, or confidence low, or STT confidence under 0.6 → report type alert.
- Minor match only, confidence high → type minor; remedies copied from the template by minor\_id (the LLM's text is ignored).
- Nothing matched → type general, doctor replies.
- Teach-back pass threshold, retry count (2) and alert rules live in config, so doctors can tune them.

**Demo-mode rule engine:** lowercase and normalise the transcript, match against each red flag's and minor symptom's keyword lists per language (e.g. Kannada ಕೆಂಪು / kempu = red, ನೋವು / novu = pain; Hindi laal, dard, khoon; Tamil sivappu, vali), and for discharge dictation use regex for name, age, side, language and template name. Good enough for a reliable on-camera demo; the real LLM handles free phrasing.

## API design

A versioned REST API under /api/v1, JSON in and out, audio as multipart uploads; FastAPI generates the OpenAPI docs at /docs, which doubles as API documentation for judges. Long-running steps return immediately with a status the UI polls (or later, a WebSocket push).

|  |  |  |  |
| --- | --- | --- | --- |
| Method | Path | Who | Purpose |
| POST | /api/v1/voice/transcribe | any | Upload audio (multipart), get {text, language, confidence} (real mode) |
| GET | /api/v1/templates | doctor | List templates |
| POST | /api/v1/templates/extract | doctor | Transcript → draft Template with unclear\_fields |
| POST | /api/v1/templates | doctor | Save a template (new version) |
| POST | /api/v1/discharges/extract | doctor | Transcript → draft discharge card |
| POST | /api/v1/discharges/{id}/approve | doctor | Blocked while unclear\_fields is non-empty; translates, generates audio, sends to patient and carer, schedules reminders |
| GET | /api/v1/discharges?status= | doctor | Dashboard list, alerts first |
| GET | /api/v1/discharges/{id} | doctor | Card, chat, reports, timeline |
| GET | /api/v1/patient/{token} | patient | Patient home: today's reminder, care card in their language |
| GET | /api/v1/patient/{token}/messages | patient | WhatsApp-style chat |
| POST | /api/v1/patient/{token}/teachback | patient | Answer audio/transcript → score, re-explain text, new status |
| POST | /api/v1/patient/{token}/reports | patient | Symptom audio/transcript → read-back summary (pending confirmation) |
| POST | /api/v1/patient/{token}/reports/{rid}/confirm | patient | Yes/no; yes sends the English report to the doctor |
| PATCH | /api/v1/reports/{rid} | doctor | Mark seen, approve or edit remedies, send to patient |
| POST | /api/v1/reports/{rid}/reply | doctor | Doctor voice/text reply → translated to patient |
| POST | /api/v1/demo/advance-day | demo only | "Simulate next day": fires due reminders |
| GET | /api/v1/health | ops | Liveness + provider mode |

**Patient access without login:** each discharge gets an unguessable token (128-bit, URL-safe) in the patient link, the same link a WhatsApp message would carry. Tokens expire after the care episode (e.g. follow-up day + 30) and can be revoked. Staff endpoints use session auth in production (Round 2: a role switcher).

**Conventions:** errors as {error: {code, message, details}}; idempotency key header on approve and send endpoints so a double tap never sends twice; pagination by cursor; every state change writes an events row in the same transaction.

## Error handling: noise, accents, mixed languages, misheard input

The rule behind every case: **when unsure, ask again or escalate to the doctor — never guess, never reassure.** Each failure has a defined response, so the demo can show it deliberately.

|  |  |  |
| --- | --- | --- |
| Situation | Detection | What the product does |
| Background noise (ward, traffic, TV) | Browser noise suppression; low STT confidence | Transcribe anyway; if confidence < 0.6, ask the patient to repeat closer to the phone |
| Clip too short or silent | Duration < 1 s or RMS below threshold, client-side | "Sorry, I couldn't hear you clearly. Please say it again, closer to the phone." in the patient's language, no upload |
| Two failed attempts in a row | Counter per interaction | Show large icon buttons (pain, redness, bleeding, fever, swelling, vision, wound) and a "Call hospital" button |
| Mixed languages (Hinglish, Kannada + English) | STT returns mixed text | Accept as is; keep English medical words; translate the whole sentence to English for the doctor |
| Wrong language detected | Detected language ≠ preferred, or patient says "no" to read-back | Reply in the detected language; patient can say or tap their language; preference updates |
| Strong regional accent | Low confidence on specific words | Read-back confirmation catches it; doctor sees original audio beside the transcript |
| Patient says the read-back is wrong | "No" by voice or button | Ask them to say it again; after two tries, offer icon buttons |
| Doctor's dictation unclear (dose, drug, date) | unclear\_fields from extraction | Field highlighted yellow, Approve disabled until fixed; doses are never auto-filled |
| Symptom maybe a red flag | Partial match or confidence low | Treat as red flag: alert the doctor, tell the patient to visit today |
| LLM returns invalid JSON or times out | Pydantic validation, 10 s timeout | Retry once, then fall back to the rule engine and mark the report "needs review" |
| Speech provider down or no key | Provider error | Fall back to browser speech APIs; banner "Running in basic voice mode" |
| Translation uncertain | Low-confidence or untranslated medical term | Keep the English term; doctor sees original and translation side by side |
| Patient offline / poor network | Upload fails | Queue the recording in IndexedDB and retry; show "Will send when you're online" |
| Duplicate tap on Send/Approve | Idempotency key | Second request returns the first result; nothing is sent twice |

## Security, privacy and compliance

CareVoice handles health data, so the prototype uses synthetic patients only, and the production design treats consent, minimal data and auditability as features rather than paperwork. None of this needs building for Round 2 beyond the basics, but it belongs in the pitch deck's "what it depends on".

**In the Round 2 build**

- Synthetic seed data only; never record real patients for the demo video.
- No secrets in the repo: .env.example with empty values, .env in .gitignore, a secret-scanning check in CI (e.g. gitleaks).
- Patient links use unguessable, expiring tokens; staff pages behind a role switcher clearly labelled "demo".
- Server-side validation on every input; audio size and type limits; CORS locked to the frontend origin.

**Production design**

- **Consent:** spoken or tapped consent at discharge, in the patient's language, stored with version and timestamp; carers added only with the patient's consent.
- **Data minimisation:** store what care needs (name, phone, language, care card, reports); delete or anonymise audio after a set retention period; patients can request access and deletion.
- **Encryption:** TLS everywhere; encrypted database and bucket at rest; signed, short-lived URLs for audio.
- **Access control:** role-based (doctor, nurse, admin), scoped to one hospital; every read of a report and every change written to events.
- **Hosting:** prefer India-region cloud for health data; data-processing agreements with speech and LLM vendors, with no training on our data.
- **Regulation to check with a lawyer:** India's Digital Personal Data Protection Act, 2023 and its Rules; the Telemedicine Practice Guidelines, since doctor replies are remote communication; whether any feature could be treated as software as a medical device (keeping CareVoice to delivering the doctor's own instructions, with no diagnosis or triage scoring, is deliberate); ABDM standards if integrating with hospital records.
- **Clinical safety:** doctor approval before anything reaches a patient; red-flag matching biased towards escalation; a clinical safety review of each template; a clear "This app does not replace your doctor. In an emergency, go to the nearest hospital" message on every patient screen.

## Scalability, reliability and observability

The expensive, slow parts are speech and LLM calls, so the design keeps the API stateless and pushes that work onto queues; everything else is ordinary CRUD that Postgres handles easily. Round 2 runs in one process; the same code splits into API, worker and scheduler services without rewrites.

**Scaling path**

|  |  |  |
| --- | --- | --- |
| Stage | Load (illustrative) | Setup |
| Round 2 / pilot | 1 hospital, a few hundred discharges a month | One container, SQLite or small Postgres, in-process jobs |
| City rollout | Tens of hospitals | Stateless API behind a load balancer (2+ replicas), managed Postgres, Redis queue, separate workers for STT/TTS/LLM, object storage + CDN for audio |
| National | Hundreds of hospitals, many languages | Autoscaled workers per job type, Postgres read replicas and partitioned events/messages by month, per-tenant rate limits, regional failover |

**Keeping costs and latency down**

- Translate and synthesise each template once per language and cache the audio; only extra instructions and doctor replies need live calls.
- Use the cheapest model that passes the eval set for each task; route only symptom analysis to a stronger model.
- Store audio compressed (opus/MP3), with lifecycle rules moving old audio to cold storage, then deleting it per retention policy.
- Target latencies: read-back after a patient speaks in under 5 s; report on the doctor's dashboard in under 10 s.

**Reliability**

- Jobs are idempotent with retries and exponential backoff; failed jobs go to a dead-letter queue the team reviews.
- Red-flag alerts never depend on one channel: dashboard + push/SMS to the doctor in production, with an escalation if unseen after a set time.
- Provider failover: if the primary speech or LLM provider errors, switch to the secondary, then to basic mode.
- Daily backups with point-in-time recovery; tested restore.

**Observability**

- Structured JSON logs with a request id that follows a voice note through every stage (no raw health data in logs).
- Metrics: STT confidence, read-back rejection rate, teach-back pass rate, alert time-to-seen, provider latency and error rate, cost per discharge.
- Error tracking (e.g. Sentry) on frontend and backend; uptime check on /api/v1/health.
- An AI eval set: real-style recordings in each language with expected matches, run in CI before any prompt or model change.

## Repo structure, environment and GitHub rules

One public monorepo that judges start with docker compose up and open on port 3000, with no keys and no .env. The README is part of the submission: it should get someone from clone to the demo flow in under five minutes.

```
carevoice/
  README.md              # what it is, demo video, docker compose up, architecture, team
  .env.example           # every variable with placeholders; app runs without .env
  docker-compose.yml     # one service, port 3000
  Dockerfile             # builds React, serves it + API from FastAPI
  Makefile               # make dev | test | lint | seed | reset
  .github/workflows/ci.yml
  docs/
    spec.md              # this doc, exported as Markdown
  backend/
    requirements.txt
    app/
      main.py            # creates app, loops ENABLED_MODULES, serves static React build
      core/              # config.py, db.py, events.py (bus + audit log), errors.py, security.py
      modules/
        templates/       # router.py service.py schemas.py models.py tests/
        discharges/
        delivery/
        teachback/
        reports/
        outcomes/        # alerts, remedies, doctor replies
        reminders/
        timeline/
        demo/            # seed, reset, simulate next day
      providers/         # base.py, registry.py, stt/ tts/ translate/ llm/ (demo_*, real_*)
      channels/          # base.py, in_app.py (whatsapp.py, sms.py later)
      ai/
        registry.py
        tasks/           # extract_template/ extract_discharge/ score_teachback/ analyse_symptom/
      rules/
        lexicons/        # kn.yaml hi.yaml ta.yaml en.yaml
        extractors.py
      seed/              # hospitals, doctors, templates, translations, patients (JSON)
    tests/               # cross-module and eval tests, fixtures/
  frontend/
    src/
      app/               # App.tsx, routes.ts, providers (query client, i18n)
      shared/            # MicButton, Recorder, speech.ts, AudioPlayer, TypeInstead, Layout, api client, generated types
      features/
        role-picker/
        doctor-dashboard/
        discharge/
        templates/
        patient-home/
        chat/
        teachback/
        report/
        outcomes/
        timeline/
      i18n/              # en.json kn.json hi.json ta.json
```

**Docker setup: one service, one port**

A multi-stage Dockerfile builds the React app, then copies the static files into the Python image; FastAPI serves the API under /api and the React app for every other path, all on port 3000. One service means one port, no CORS and no proxy to misconfigure.

```yaml
# docker-compose.yml
services:
  app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - PROVIDER_MODE=demo   # works with no .env file
    volumes:
      - carevoice-data:/app/data
volumes:
  carevoice-data:
```

```dockerfile
# Dockerfile
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY --from=web /web/dist ./static
EXPOSE 3000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000"]
```

**Startup rules in code**

- config.py gives every setting a default (PROVIDER\_MODE=demo, SQLite at /app/data/carevoice.db); a missing .env is never an error.
- On startup: create tables if missing, seed demo data if the database is empty, log CareVoice ready on :3000 (demo mode).
- / opens the main screen directly (role picker: Doctor / Patient), never a blank page or API JSON.
- Any feature asking for a real provider without a key shows a "Key not set, using demo mode" badge instead of failing.
- Pin dependency versions (package-lock.json, requirements.txt with versions) so the build is the same on the judges' machine.
- A Docker health check on /api/v1/health.
- Microphone access only works on localhost or HTTPS. Judges opening localhost:3000 is fine; for the live link, use HTTPS. Every voice step also has a small "type instead" box, so the flow still works if a mic or browser speech is unavailable.

**Environment variables (.env.example)**

|  |  |  |
| --- | --- | --- |
| Variable | Default | Purpose |
| PROVIDER\_MODE | demo | demo = no keys; real = use providers below |
| DATABASE\_URL | sqlite:////app/data/carevoice.db | Postgres URL in production |
| MEDIA\_DIR / S3\_BUCKET | ./media / empty | Audio storage |
| STT\_PROVIDER, TTS\_PROVIDER, TRANSLATE\_PROVIDER | browser | e.g. sarvam, bhashini |
| SARVAM\_API\_KEY, BHASHINI\_API\_KEY | empty | Only in real mode |
| LLM\_PROVIDER, LLM\_MODEL, LLM\_API\_KEY | empty | Only in real mode |
| FRONTEND\_ORIGIN | http://localhost:5173 | CORS |
| DEMO\_ENDPOINTS | true | Enables Simulate next day; false in production |

**GitHub rules for submission**

- ☐ Repo public.
- ☐ docker compose up on a clean machine builds and starts with no .env and no keys; http://localhost:3000 shows CareVoice's main screen.
- ☐ .env.example lists every variable with placeholder values; .env is in .gitignore.
- ☐ No keys anywhere in history (run gitleaks before making it public; if a key was ever committed, rotate it, since deleting the file doesn't remove history).
- ☐ Our own code, well over 300 lines, written during the hackathon; the commit history shows it (no big template dump).
- ☐ README: problem in two lines, demo video link, docker compose up quick start, demo mode vs real mode, architecture, team, licence (MIT).
- ☐ CI green on main: lint, type-check, tests, and a docker compose build.
- ☐ A friend outside the team clones and starts it, following only the README.
- ☐ Tag the submitted commit round2-submission.

## Build parts: build, test, push, repeat

Fourteen parts, in order; each leaves the app starting with docker compose up and adds one thing a person can see or test. Parts 0–9 are the core flow (P0); 10–13 are added value. Never start a part until the previous one is pushed.

### Part 0 — Skeleton that already passes the rules

- **Build:** monorepo layout; FastAPI app with /api/v1/health; React + Vite + Tailwind + shadcn/ui app with a role picker page ("I'm a doctor" / "I'm a patient"); multi-stage Dockerfile and docker-compose.yml serving both on port 3000; .env.example; Makefile; CI running lint, tests and docker compose build.
- **Done when:** fresh clone + docker compose up with no .env shows the role picker on localhost:3000; /api/v1/health returns {status: ok, mode: demo}; CI green.
- **Commit:** feat: project skeleton, docker on :3000

### Part 1 — Core: config, database, events, seed

- **Build:** core/config.py (pydantic-settings, every value defaulted); core/db.py (SQLAlchemy, SQLite default, Postgres via DATABASE\_URL); all models from "Data model"; core/events.py (in-process bus + writes every event to the events table); module loader with register(app, bus); modules/demo seeds from JSON on first start and exposes POST /api/v1/demo/reset.
- **Done when:** pytest covers models, seeding is idempotent, reset restores seed data, bus delivers an event to a test listener and writes it to events.
- **Commit:** feat: core config, models, event bus, seed

### Part 2 — Providers and channels with demo defaults

- **Build:** provider interfaces + registry (STT, TTS, Translator, LLM); demo implementations (server side: echo transcript, pre-translated lookup, rule-based LLM stand-in); key\_not\_set status; channels/in\_app.py; GET /api/v1/system/status listing each provider's mode.
- **Done when:** unit tests per provider; selecting a real provider without a key falls back to demo and reports key\_not\_set.
- **Commit:** feat: provider and channel registries, demo mode

### Part 3 — Rules engine and AI tasks

- **Build:** lexicons for kn, hi, ta, en (red flags, minor symptoms, negations such as "novu illa", "dard nahi"); regex discharge extractor (name, age, side, language, template, extras, unclear doses); teach-back scorer; symptom analyser; decision rules (alert / minor / general); AI task registry with the four task folders, rules as fallback.
- **Done when:** eval fixtures (at least 10 phrases per language, including code-mixed and negations) pass; no red-flag phrase in the set is missed.
- **Commit:** feat: rules engine, AI task registry, eval set

### Part 4 — Shared voice UI

- **Build:** shared/ MicButton (big, pulsing while recording), Recorder (MediaRecorder, 60 s cap, short/silent clip check), speech.ts wrapping Web Speech API recognition and speechSynthesis with language codes, AudioPlayer, TypeInstead box, i18n setup with en/kn/hi/ta strings, API client with generated types; a hidden /dev/voice page to try them.
- **Done when:** on /dev/voice you can speak Kannada and see the transcript, hear text spoken back, and type instead; Vitest covers the clip check.
- **Commit:** feat: shared voice components and i18n

### Part 5 — Doctor: templates and dictated discharge

- **Build:** modules/templates (list, view, version; voice-create is optional at the end of the part); modules/discharges (extract → draft card, approve blocked while unclear\_fields exist, idempotent approve, publishes discharge.approved); doctor pages: template list, "New discharge" with mic → editable card with yellow unclear fields → Approve.
- **Done when:** saying the Ramesh sentence fills the card; an unclear dose turns yellow and blocks Approve; API tests cover the block and idempotency.
- **Commit:** feat: dictated discharge with approval gate

### Part 6 — Delivery to patient and carer

- **Build:** modules/delivery listens to discharge.approved: builds the care card in the patient's language (seeded translations), creates messages for patient and carer, issues patient link tokens, sends through enabled channels; patient pages: home (big mic, care card, Call hospital button) and WhatsApp-style chat with replayable voice notes (browser TTS in demo).
- **Done when:** after Approve, the patient link shows the Kannada card with red flags first and plays it aloud; the carer's link shows the same.
- **Commit:** feat: deliver care card to patient and carer

### Part 7 — Spoken teach-back

- **Build:** modules/teachback: question in the patient's language, score answer, re-explain missed flags, two tries, status understood or needs\_followup, publishes teachback.scored; patient teach-back screen.
- **Done when:** a partial answer triggers re-explanation; a full answer marks Understood on the doctor's dashboard; two failures mark Needs follow-up.
- **Commit:** feat: spoken teach-back

### Part 8 — Symptom report to the doctor

- **Build:** modules/reports: patient speaks → analyse → read-back in their language → confirm yes/no → English report saved, publishes report.confirmed; carer reports marked as such; doctor dashboard (alerts first, filter by status, search) and report page (audio, native transcript beside English, symptoms, recovery day, medicines).
- **Done when:** the Kannada red-eye phrase produces a confirmed report the doctor can read in English; saying "no" to the read-back asks again.
- **Commit:** feat: voice symptom reports with read-back

### Part 9 — Outcomes: alert, remedy, reply

- **Build:** modules/outcomes listens to report.confirmed: red flag or low confidence → alert + patient safety message; minor → remedy from template awaiting doctor approval → translated to patient; general → doctor reply (text or voice, translated); mark alert handled; close episode.
- **Done when:** all three branches work on screen; the remedy text always comes from the template; the doctor's reply reaches the patient in their language.
- **Commit:** feat: alerts, template remedies, doctor replies

### Part 10 — Reminders and timeline

- **Build:** modules/reminders schedules messages from the template; demo "Simulate next day" fires due reminders; today's reminder on the patient home; modules/timeline (listens to every event) and a read-only timeline on the doctor's patient page.
- **Done when:** simulating day 3 plays the eye-drops reminder; the timeline lists every step with times.
- **Commit:** feat: reminders and patient timeline

### Part 11 — Error handling and resilience

- **Build:** every row of the error-handling table: retry prompt, icon grid and Call hospital after two failures, language switch, low-confidence escalation, offline queue (IndexedDB), friendly error states, provider failover messages.
- **Done when:** each row of the error-handling table can be triggered and shows the defined response.
- **Commit:** feat: error handling for noise, language and network

### Part 12 — Real providers (optional, needs keys)

- **Build:** real STT/TTS/translation (Sarvam AI or Bhashini) and LLM adapters behind the registry; keys only from environment; audio stored and cached.
- **Done when:** with keys set locally, the flow works with real speech; without keys, nothing changes and the badge says "Key not set, using demo mode". Never commit keys.
- **Commit:** feat: real speech and LLM providers

### Part 13 — Polish and submission

- **Build:** README, accessibility (large text, contrast, labels), mobile layout, demo reset button in the header, emergency disclaimer on patient screens, final seed data, clean-machine Docker test, tag round2-submission.
- **Done when:** a friend clones and runs it from the README alone; every item in the manual test checklist passes.
- **Commit:** chore: polish and submission

## Build plan and team split

We have from Thursday 27 Nov evening to **Sunday 30 Nov, 11:59 pm**, about three and a half days. The rule: the core flow works end to end in demo mode by Saturday afternoon, and Sunday is for recording, the deck and buffer, not new features. Submit by Sunday 9 pm; the submission can't be changed after.

**Roles** (swap names in): **Backend & AI** owns FastAPI, data model, providers, rule engine. **Frontend** owns doctor and patient screens, mic, recorder, chat. **Product & content** owns seed templates and translations, test recordings, demo script, deck, video, README, and tests the flow every few hours.

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| When | Backend & AI | Frontend | Product & content | Gate |
| Thu 27 Nov evening | Part 0, Part 1 | Part 0 (React shell, role picker) | Templates with your doctor contact: red flags, minor symptoms, remedies, keywords in kn/hi/ta (seed JSON for Part 1) | Docker starts on :3000 for all three |
| Fri 28 Nov | Parts 2, 3, then 5 (backend) | Part 4, then 5 (doctor screens) | Patient strings in kn/hi/ta; 10 test phrases per language for the Part 3 eval set; deck draft | Doctor dictates a discharge and approves |
| Sat 29 Nov morning | Parts 6, 7, 8 (backend) | Parts 6, 7, 8 (patient + report screens) | Test every pushed part against its "Done when"; README draft | **Core flow works end to end** |
| Sat 29 Nov afternoon–night | Part 9, then 10; Part 12 only if all else is done | Part 9, then 11 | Demo script final; deck finished; live link only if easy | Feature freeze at midnight |
| Sun 30 Nov | Part 13, bug fixes, clean-machine Docker test, tag | Part 13, mobile check on a real Android phone | Record and upload video; export deck PDF; friend test | **Submit by 9 pm** |

**If behind schedule, cut in this order:** Part 12 (real providers) → voice-created templates in Part 5 → Part 10 (reminders, timeline) → doctor reply in Part 9 → the less common rows of Part 11. Never cut Parts 0–8 or the red-flag alert in Part 9.

## Testing and QA

Test the parts that decide patient safety hardest: red-flag matching, the approve gate and the escalate-when-unsure rules. A fresh clone with no keys must pass the whole flow before we submit.

**Automated**

- **Unit (pytest):** discharge regex extraction; keyword matcher per language (red flags, minor symptoms, negations like "novu illa" / "dard nahi" = no pain); teach-back scoring at 0%, 74%, 75%, 100%; decision rules (low confidence → alert).
- **API (pytest + httpx):** approve blocked while unclear\_fields exist; idempotent approve; patient token expiry; report confirm → doctor sees it; every state change writes an event.
- **AI eval set:** 30–50 transcripts across Kannada, Hindi, Tamil, English and code-mixed, each labelled with expected flag/minor ids. Track recall on red flags (target: no missed red flags in the set) before any prompt change.
- **Frontend (Vitest + Playwright):** one smoke test that walks discharge → patient chat → teach-back → report → doctor alert in demo mode, run in CI.

**Manual checklist before recording**

- ☐ Fresh clone on a machine that has never run the project: docker compose up with no .env, no keys; port 3000 shows the CareVoice main screen, not a default server page.
- ☐ A friend outside the team does the same, following only the README.
- ☐ Whole flow works in demo mode inside the container.
- ☐ "Key not set" badge appears, and nothing breaks, when real mode is selected without keys.
- ☐ Chrome on a real Android phone: mic permission, recording, playback, layout.
- ☐ Each demo language: speak the scripted phrase three times; read-back correct each time.
- ☐ Noisy room test (TV or traffic on): retry prompt appears, then icon grid after two failures.
- ☐ "Type instead" box completes the flow without a microphone.
- ☐ Unclear dose in dictation: field turns yellow, Approve disabled.
- ☐ Red-flag phrase: alert appears on doctor dashboard, patient hears the visit-today message.
- ☐ Minor phrase: remedy from template appears, doctor approves, patient receives it in their language.
- ☐ Live link (if any) works over HTTPS in an incognito window.

## Demo video script (under 3 minutes)

The video's job is to show voice doing the real work, live, in Indian languages, including one thing going wrong and being handled. Split screen: doctor's laptop on the left, patient's phone on the right. Real voices, no music over speech, captions in English.

|  |  |  |
| --- | --- | --- |
| Time | Screen | What happens / what's said |
| 0:00–0:15 | Title card, then a doctor quote | "Patients come back saying 'we were never told'." One line on the problem: instructions given once, in English, at discharge. |
| 0:15–0:40 | Doctor dashboard | Doctor taps mic: "Ramesh, 68, cataract right eye, standard template, diabetic so check sugar daily, language Kannada." Card fills; one dose shows yellow, doctor fixes it, taps Approve. |
| 0:40–1:05 | Patient phone, chat | Kannada text card arrives, red flags first; voice note plays in Kannada. |
| 1:05–1:30 | Patient phone, teach-back | App asks in Kannada when to come back. Patient answers, missing one flag; app re-explains it; second answer passes; doctor dashboard shows Understood. |
| 1:30–1:40 | "Simulate next day" | Day 3 reminder plays: eye drops + "Is your eye red or painful? Tap the mic and tell me." |
| 1:40–2:15 | Patient phone, big mic | Patient: "Kannu tumba kempagide, novu ide." Read-back in Kannada, patient says yes. Doctor's screen: red Alert with audio, Kannada transcript, English translation, recovery day, medicines. Patient hears "please visit the hospital today". |
| 2:15–2:35 | Hindi patient (Sunita) | Minor symptom in Hindi → remedy from template suggested → doctor approves → Hindi voice note arrives. Shows a second language. |
| 2:35–2:45 | Noisy room | TV on: "Sorry, I couldn't hear clearly" → after two tries, icon grid appears. |
| 2:45–3:00 | Timeline + close | Time-stamped record of everything sent and confirmed. "CareVoice: the doctor speaks once, the patient understands, and both have a record." |

**Recording tips:** rehearse with the exact phrases from the test set; record each segment separately and cut together; keep the cursor slow; show the browser address bar once so it's clearly a real web app; check audio levels so voice notes are audible.

## Pitch deck outline (PDF)

Judges read the words, not the pictures, so every slide states its point in full sentences; screenshots and diagrams only support text that already makes the point. Eight slides follow the four required parts in order, with a title, a walkthrough and a closing slide.

- **Title:** CareVoice: the doctor speaks once, the patient understands. Team Sicarios, Healthcare access. One sentence on what it does.
- **Problem and solution (required part 1):**

- Problem, as text: patients leave hospital with care instructions given once, verbally, often in English; many can't read a printed sheet, eye-surgery patients can't read at all, carers weren't in the room, danger signs are missed, and doctors have no record when families say "we were never told". Include your doctor contact's own words.
- Solution, as text: the doctor dictates once using reusable templates; patients and carers hear instructions in their own language; spoken teach-back confirms understanding; patients report symptoms by voice; doctors get English reports, red-flag alerts and a record. Never diagnoses; remedies only from the doctor's template.

- **Who it's for and how many (required part 2):** users written out (patients after any treatment needing home care, carers, doctors and nurses, hospitals as buyers). Size, as text: over 98 lakh cataract surgeries in 2024–25; roughly 5 crore hospital stays a year (our estimate from NSS-based data); first users: one hospital department, a few hundred patients a month.
- **What it depends on (required part 3):** one line per dependency, each with what happens if it gets costly or stops working:

- Indian-language speech-to-text and text-to-speech (Sarvam AI or Bhashini): if costly, cache template audio per language so only short extras need live calls; if down, fall back to browser speech, then to tap-based icons and text.
- LLM for extraction, matching and reports (Claude, Gemini or OpenAI via one adapter): if costly, use smaller models per task and the rule engine for common phrases; if down, the rule engine keeps the core flow running and reports are marked "needs review".
- Translation: templates translated once and verified, so cost is per template, not per patient.
- WhatsApp Business API (production): if costly or blocked, the web link works over SMS; an IVR phone-call channel is the next fallback.
- Cloud hosting and storage: standard Docker, movable between providers; audio deleted after a retention period to cap storage cost.
- Non-technical: patient consent and data-protection compliance; doctors adopting it, which needs it to be faster than talking.

- **Launch plan (required part 4):** first users through our doctor contact's department; pilot, then more departments and Bengaluru hospitals, then city-by-city; what we measure at each step and the gate to move on (from the launch section). How we reach users: doctors bring patients in at discharge, so the hospital is the channel and the buyer.
- **Product walkthrough:** the core flow in five steps as text, each with a screenshot beside it.
- **Safety and privacy:** doctor approves everything, escalates when unsure, never diagnoses; consent, minimal data, India-region hosting.
- **Team and links:** members and roles; GitHub, YouTube and live link as text URLs.

## Launch plan and business model

Launch through one doctor and one department we already have access to, prove that patients understand and complications are caught earlier, then sell to hospitals as a per-discharge service. Each phase has a gate we must pass before the next.

- **Pilot (months 0–3):** one hospital, one department (eye or obstetrics), synthetic-tested templates verified by the doctor, WhatsApp delivery to consenting patients. **Gate:** most patients pass teach-back, families play the voice notes, red-flag reports reach the doctor the same day, and doctors say discharge takes less time than before.
- **Expand (months 3–9):** more departments in the same hospital, then 3–5 hospitals or nursing homes in Bengaluru; template library grows; add Telugu, Malayalam, Marathi. **Gate:** hospitals renew after the trial period; no safety incidents traced to the app.
- **Scale (months 9+):** city-by-city rollout, integration with hospital information systems and ABDM health records, native Android widget, analytics for hospital admins. **Gate:** unit economics work (cost per discharge below price), support load manageable.

**Business model (hypotheses to test in the pilot)**

|  |  |
| --- | --- |
| Question | Hypothesis |
| Who pays | The hospital or nursing home, not the patient |
| Pricing | Per discharge, or a monthly subscription by bed count; free during the pilot |
| Why they pay | Fewer avoidable readmissions and complications coming back late, fewer disputes, better patient satisfaction, less doctor and nurse time per discharge |
| Main costs | Speech, translation and LLM calls per discharge; WhatsApp message fees; cloud hosting; support |
| Channels | Doctor referrals and medical associations; hospital chains; insurance and government-scheme hospitals later |
| Moat | Doctor-verified multilingual template library, patient-language voice data quality, trust and safety record, workflow integration |

Open question: talk to your doctor contact about who in her hospital decides on tools like this, and whether her department would run the pilot.

## Risks and open questions

The biggest risk is a missed or mistranslated red flag; the biggest hackathon risk is the demo failing live. Both are handled by the same habits: escalate when unsure, rehearse with known phrases, and keep a keyless fallback.

|  |  |  |
| --- | --- | --- |
| Risk | Type | Mitigation |
| Misheard or mistranslated symptom hides a red flag | Safety | Read-back confirmation, escalate on low confidence, keyword + LLM double check, doctor sees original audio |
| Translation changes an instruction's meaning | Safety | Templates translated once and verified by a doctor or native speaker; only short extras translated live, shown to the doctor |
| Browser speech weak for Kannada/Tamil on some devices | Demo | Test on the recording device early; fall back to typed transcript in the dev panel; real provider if keys allow |
| Core flow not finished in time | Delivery | Saturday gate; cut list in the build plan |
| Secret key leaks into the public repo | Rules | .env ignored, gitleaks in CI, demo mode default, rotate any leaked key |
| Doctors won't use it if it's slower than talking | Adoption | One-sentence discharge, seeded templates, measure doctor time from day one |
| Patients don't have smartphones or WhatsApp | Reach | Carer receives everything; IVR phone-call version as a later channel |
| Over-reliance: patient waits for the app instead of going to hospital | Safety | Emergency message on every screen; red flags always say "visit today" |

**Open questions**

- ☒ Read the full Round 2 rules: done; Docker, port, no-keys and deck rules are now in this doc.
- ☐ Confirm with your doctor contact: the procedure to demo, its real red flags, minor symptoms and remedies, and whether we can quote her.
- ☐ Decide real-mode providers and check free tiers: Sarvam AI vs Bhashini for speech; which LLM.
- ☐ Who records the patient voices in Kannada, Hindi and Tamil for the demo?
- ☐ Live link: worth it only if the Docker image runs on a free HTTPS host (Render, Railway or Fly) by Saturday night; skip otherwise.

## Sources

- Over 98 lakh cataract surgeries performed in FY25 (IANS via Lokmat Times)
- Hospitalisation rate in India, 1995–2014 (BMJ Open): 3,699 per 100,000 in 2014; the roughly 5 crore a year figure is our own estimate from it.
