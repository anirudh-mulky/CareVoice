# CareVoice

Patients leave hospital with care instructions given once, verbally, in English. CareVoice lets
the doctor speak the discharge once; the patient hears it in their own language, and anything the
patient says about a symptom comes back to the doctor as an English report.

> Round 2 build in progress, one part at a time. See [docs/spec.md](docs/spec.md).

## Quick start

Needs only Docker. No `.env` file and no API keys.

```bash
git clone https://github.com/anirudh-mulky/CareVoice.git
cd CareVoice
docker compose up --build
```

Open http://localhost:3000. Health check: http://localhost:3000/api/v1/health. API docs:
http://localhost:3000/api/docs.

## Demo mode and real mode

By default `PROVIDER_MODE=demo`: speech runs in the browser and a rule engine stands in for the
LLM, so nothing needs a key. `.env.example` lists every setting; copy it to `.env` only to override.

## Develop

```bash
make dev    # API on :8000, Vite on :5173 (proxies /api)
make test   # pytest + vitest
make lint   # ruff, mypy, eslint, tsc
```

## Layout

- `backend/` FastAPI app (Python 3.11). Serves the API under `/api` and the React build for every
  other path, on port 3000.
- `frontend/` React + Vite + TypeScript + Tailwind + shadcn/ui.
- `docs/spec.md` the build spec.

## Licence

MIT
