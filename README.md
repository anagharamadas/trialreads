# TrialReads

A full-stack reading companion: summarise books, manage a personal library, ask
questions about it in plain English, get recommendations, and build ordered
"shelves" (reading lists) with an AI curation agent — all with per-user data
isolation, production observability, and an LLM evaluation pipeline.

Built in phases as a learning project: **P1** library + Row Level Security ·
**P2** shelves + curation agent · **P3** observability (traces/metrics/logs,
Langfuse) · **P4** eval pipeline.

## Features

- **Book summaries** — chapter-by-chapter summary of a book's first three chapters (`/summarise`).
- **Personal library** — CRUD over your book collection, protected by Postgres Row Level Security.
- **Natural-language library Q&A** — ask "how many books did I finish in 2023?"; a LlamaIndex text-to-SQL engine answers over a per-user, RLS-scoped view (`/library/query`).
- **Recommendations** — 5 similar books with a reason and an Amazon search link (`/recommend`).
- **Shelves** — Goodreads-style collections (`shelves` + `shelf_books`), independent of the library, with optional links back to owned books.
- **Curation agent** — a LangGraph ReAct agent that clarifies your goal, researches real books via Google Books, and proposes an ordered reading list; every suggested book is re-validated against Google Books before it's shown (`/shelves/{id}/curate`).
- **Observability** — OpenTelemetry traces/metrics/logs (Jaeger locally, Grafana Cloud in prod), Langfuse LLM tracing, Sentry error monitoring, Vercel Speed Insights.
- **Eval pipeline** — golden datasets + LLM-as-judge scoring for all four AI features, run as Langfuse experiments (see [`backend/evals/`](backend/evals/README.md)).

## Tech stack

| Layer | Tech |
|-------|------|
| **Backend** | FastAPI · LangChain / LangGraph · LlamaIndex (text-to-SQL) · SQLAlchemy · OpenAI `gpt-4o-mini` |
| **Frontend** | Next.js 14 (App Router) · React 18 · TypeScript · Tailwind CSS · `@supabase/supabase-js` |
| **Database / Auth** | Supabase (Postgres + Row Level Security + Auth/JWT) |
| **Observability** | OpenTelemetry · Jaeger / Grafana Cloud · Langfuse · Sentry · Vercel Speed Insights · k6 |
| **Deploy** | Backend → Render · Frontend → Vercel |

## Repository layout

```
trialreads/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── main.py          # app entry, CORS, /health, router wiring
│   │   ├── config.py        # typed settings from backend/.env
│   │   ├── auth.py          # Supabase JWT verification
│   │   ├── db.py            # pooled engine + per-request RLS connection
│   │   ├── telemetry.py     # OpenTelemetry setup (traces/metrics/logs)
│   │   ├── llm_observability.py  # Langfuse (LangChain/LangGraph paths)
│   │   ├── rate_limit.py    # per-user daily AI cap
│   │   ├── routers/         # library, ai, shelves, covers
│   │   └── services/        # summariser, recommendations, library_query,
│   │                        #   curation_agent, google_books
│   └── evals/               # Phase 4 eval pipeline (see its README)
├── frontend/                # Next.js app (login, signup, shelves, book, chat)
├── supabase/                # schema.sql (library + RLS) · shelves.sql
├── k6/                      # load tests
├── OBSERVABILITY.md         # observability runbook
├── DEPLOY.md                # Render + Vercel deploy guide
└── render.yaml              # backend service definition
```

## Quick start

### Prerequisites
- Python 3.12+, Node.js 18.17+
- A Supabase project (Postgres + Auth)
- OpenAI API key; optionally a Google Books API key (better curation/cover results)

### 1. Database (Supabase)
In the Supabase dashboard → **SQL Editor**, run:
```
supabase/schema.sql     # library table + my_library view + RLS + ai_usage
supabase/shelves.sql    # shelves + shelf_books + RLS
```
Both are idempotent and include a manual isolation test you should run once.

### 2. Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in OPENAI_API_KEY, SUPABASE_*, DATABASE_URL
uvicorn app.main:app --reload
# API on http://localhost:8000  ·  docs at /docs  ·  liveness at /health
```

### 3. Frontend
```bash
cd frontend
npm install
cp .env.example .env.local  # NEXT_PUBLIC_SUPABASE_URL / _ANON_KEY / _API_URL
npm run dev
# App on http://localhost:3000
```

## API surface

All routes are under the API root (no `/api` prefix). Auth is a Supabase JWT in
the `Authorization: Bearer` header; the user id comes from the verified token,
never the request body.

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/health` | Liveness (no auth/DB), version, uptime, OTel status |
| `GET/POST/PUT/DELETE` | `/library`, `/library/{id}` | Library CRUD |
| `POST` | `/library/query` | Natural-language → SQL over your library |
| `POST` | `/summarise` | Chapter-by-chapter book summary |
| `POST` | `/recommend` | 5 similar-book recommendations |
| `GET`  | `/covers` | Book cover lookup (Google Books) |
| `GET/POST/PUT/DELETE` | `/shelves`, `/shelves/{id}` | Shelf CRUD |
| `GET/POST/PUT/DELETE` | `/shelves/{id}/books`… | Shelf-item management (incl. bulk add) |
| `POST` | `/shelves/{id}/curate` | Curation agent turn (clarify or propose a list) |

## Data model & isolation

- **`library`** — your books (title, author, status, year). `my_library` is a
  per-user view exposing only your rows; the text-to-SQL engine is pointed at it.
- **`shelves` / `shelf_books`** — ordered reading lists; `shelf_books` may link
  back to an owned `library` row.
- **`ai_usage`** — per-user daily AI-call counter for rate limiting.

Every user-facing table has Row Level Security scoped to `auth.uid()`. The
text-to-SQL path is defense-in-depth: the LLM only sees `my_library`, queries run
on a non-pooled connection stamped with the caller's JWT claims (`SET ROLE
authenticated`), so Postgres RLS physically restricts every statement to the
caller's rows.

## Observability

`backend/app/telemetry.py` exports OpenTelemetry traces/metrics/logs over
OTLP — no-op unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set, so backends are a
config-only swap:

- **Local:** `docker compose -f backend/docker-compose.jaeger.yml up -d`, then set
  `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` (+ `OTEL_LOGS_EXPORT=false`,
  `OTEL_METRICS_EXPORT=false` — Jaeger is traces-only). UI at http://localhost:16686.
- **Production:** paste the values Grafana Cloud's OTLP setup generates.
- **LLM traces / cost:** set `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`.

See [`OBSERVABILITY.md`](OBSERVABILITY.md) for the full runbook.

## Eval pipeline

`backend/evals/` evaluates the four AI features (NL→SQL, summaries, recommend,
curation). Each has a golden dataset, an LLM-as-judge, and a **negative control**
that guards the judge (a deliberately wrong case the judge must reject). Runs
either offline (`python -m evals.run_eval`, Markdown report) or as Langfuse
dataset experiments (`python -m evals.<feature>_experiment`). See
[`backend/evals/README.md`](backend/evals/README.md).

## Deployment

Backend deploys to **Render** (`render.yaml`), frontend to **Vercel**. Set
`CORS_ORIGINS` to the Vercel domain and `CORS_ALLOW_LOCALHOST=false` in
production. Full walkthrough in [`DEPLOY.md`](DEPLOY.md).

## Environment variables

Templates: `backend/.env.example`, `frontend/.env.example` (both gitignored once
copied). Highlights — backend: `OPENAI_API_KEY`, `SUPABASE_URL` /
`SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_JWT_SECRET`,
`DATABASE_URL`, `GOOGLE_BOOKS_API_KEY`, `CORS_ORIGINS`, optional `OTEL_*` /
`LANGFUSE_*` / `SENTRY_DSN`. Frontend: `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL`. Never put the service-role
or OpenAI key in the frontend — only `NEXT_PUBLIC_*` reaches the browser.

## License

MIT
