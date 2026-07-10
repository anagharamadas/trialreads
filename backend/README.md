# TrialReads Backend

FastAPI service for TrialReads: book summaries, a personal library with
natural-language (text-to-SQL) querying, recommendations, and an AI shelf-curation
agent — all over Supabase Postgres with Row Level Security.

See the [root README](../README.md) for the whole project; this covers the
backend only.

## What it does

- **Summaries** — chapter-by-chapter summary of a book's first three chapters.
- **Library** — CRUD over the user's books, scoped by Postgres RLS.
- **Text-to-SQL** — natural-language questions answered over a per-user, RLS-scoped
  view via LlamaIndex.
- **Recommendations** — 5 similar books with reasons + Amazon search links.
- **Shelves + curation agent** — ordered reading lists built by a LangGraph ReAct
  agent that researches and re-validates every book against Google Books.

## Layout

```
app/
├── main.py              # FastAPI app, CORS, /health, telemetry + router wiring
├── config.py            # typed settings loaded from backend/.env (pydantic-settings)
├── auth.py              # Supabase JWT verification → current user id
├── db.py                # pooled engine (CRUD) + rls_connection() (text-to-SQL)
├── rate_limit.py        # per-user daily AI-call cap (ai_usage table)
├── schemas.py           # Pydantic request/response models
├── telemetry.py         # OpenTelemetry traces/metrics/logs (OTLP)
├── llm_observability.py # Langfuse callback config (LangChain/LangGraph paths)
├── routers/
│   ├── library.py       # /library CRUD + /library/query (text-to-SQL)
│   ├── ai.py            # /summarise, /recommend
│   ├── shelves.py       # /shelves CRUD + items + /shelves/{id}/curate
│   └── covers.py        # /covers (Google Books lookup)
└── services/
    ├── summariser.py        # LangChain summary chain
    ├── recommendations.py   # recommendation chain + parser
    ├── library_query.py     # LlamaIndex text-to-SQL over my_library (RLS)
    ├── curation_agent.py    # LangGraph ReAct agent + grounding
    └── google_books.py      # Google Books search / validate

evals/                   # Phase 4 eval pipeline (see evals/README.md)
scripts/                 # one-off utilities (e.g. import_existing_library.py)
docker-compose.jaeger.yml # local trace lab
```

There is no ORM migration tool or `init_db` — the schema lives in
[`../supabase/schema.sql`](../supabase/schema.sql) and
[`../supabase/shelves.sql`](../supabase/shelves.sql), applied via the Supabase SQL
editor. SQLAlchemy is used for queries and RLS connection management, not DDL.

## Setup

Requires Python 3.12+ and a Supabase project with the schema applied (run the two
`supabase/*.sql` files first).

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in the values below
uvicorn app.main:app --reload
# API on http://localhost:8000 · Swagger at /docs · ReDoc at /redoc
```

## Endpoints

Auth is a Supabase JWT (`Authorization: Bearer <token>`); the user id comes from
the verified token, never the body. No global `/api` prefix.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness (no auth/DB): status, version, uptime, OTel status |
| `GET` | `/library` | List the user's books |
| `POST` | `/library` | Add a book |
| `PUT` / `DELETE` | `/library/{book_id}` | Update / delete a book |
| `POST` | `/library/query` | Natural-language → SQL over the user's library |
| `POST` | `/summarise` | Chapter-by-chapter summary |
| `POST` | `/recommend` | 5 similar-book recommendations |
| `GET` | `/covers` | Book cover lookup |
| `GET` / `POST` | `/shelves` | List / create shelves |
| `PUT` / `DELETE` | `/shelves/{id}` | Update / delete a shelf |
| `GET` / `POST` | `/shelves/{id}/books` | List / add shelf items (incl. bulk) |
| `PUT` / `DELETE` | `/shelves/{id}/books/{book_id}` | Update / remove a shelf item |
| `POST` | `/shelves/{id}/curate` | Curation-agent turn (clarify or propose a list) |

## Isolation model (text-to-SQL)

The highest-risk path is defense-in-depth: the LLM is pointed only at the
`my_library` view (which self-filters to `auth.uid()` and hides `user_id`),
queries run on a **non-pooled** connection stamped with the caller's JWT claims
(`SET ROLE authenticated` + `request.jwt.claims`), and `NullPool` + per-request
`dispose()` means no connection state is ever reused across users. For a leak, the
view filter, base-table RLS, and table scoping would all have to fail at once.

## Environment variables

Copy `.env.example` → `.env` (gitignored). Key values:

| Var | Purpose |
|-----|---------|
| `OPENAI_API_KEY` | OpenAI (`gpt-4o-mini`) |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` | Supabase API |
| `SUPABASE_JWT_SECRET` | Verify the JWT the frontend sends |
| `DATABASE_URL` | Supabase Postgres connection string |
| `GOOGLE_BOOKS_API_KEY` | Covers + curation research/grounding |
| `DAILY_AI_LIMIT` | Per-user daily AI-call cap (default 50) |
| `CORS_ORIGINS` / `CORS_ALLOW_LOCALHOST` | Allowed frontend origins |
| `DEBUG` / `PORT` / `HOST` / `LOG_LEVEL` | Server |
| `OTEL_*` | OpenTelemetry export (optional; see below) |
| `LANGFUSE_*` | Langfuse LLM tracing (optional) |
| `SENTRY_DSN` | Sentry error monitoring (optional) |

## Observability

`telemetry.py` exports OTel traces/metrics/logs over OTLP — no-op unless
`OTEL_EXPORTER_OTLP_ENDPOINT` is set. Local Jaeger:

```bash
docker compose -f docker-compose.jaeger.yml up -d   # UI http://localhost:16686
# in .env: OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
#          OTEL_LOGS_EXPORT=false  OTEL_METRICS_EXPORT=false  (Jaeger is traces-only)
```

Grafana Cloud in production is a config-only swap. See
[`../OBSERVABILITY.md`](../OBSERVABILITY.md).

## Evaluation

AI-feature quality is checked by the eval pipeline in [`evals/`](evals/README.md)
(golden datasets + LLM-as-judge + negative controls), not a unit-test suite.
Manual QA notes live in [`../QA-phase2.md`](../QA-phase2.md).

## Deployment

Deploys to Render via [`../render.yaml`](../render.yaml); see
[`../DEPLOY.md`](../DEPLOY.md). Production runs under a process manager, e.g.:

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

Set `CORS_ALLOW_LOCALHOST=false` and `CORS_ORIGINS` to the Vercel domain in prod.
