# TrialReads — Observability Runbook (Phase 3)

Everything code-side is implemented and env-guarded: **with no observability
env vars set, the app behaves exactly as before** (plus structured JSON logs on
stdout). Each signal switches on via configuration only.

**Stack:** OpenTelemetry (traces + metrics + logs) → Grafana Cloud (Tempo /
Mimir / Loki) · Langfuse (LLM detail) · Vercel Speed Insights (Web Vitals) ·
Sentry (unchanged, error alerting) · Grafana Synthetics + k6 (probing / load).

**Where the code lives:**

| File | What |
|---|---|
| `backend/app/telemetry.py` | ALL OTel config: traces, metrics, logs, JSON logging, auto-instrumentation, cold-start attrs |
| `backend/app/llm_observability.py` | Langfuse helper (LangChain/LangGraph paths), env-guarded |
| `backend/docker-compose.jaeger.yml` | Local trace lab (M1) |
| `observability/grafana-dashboard.json` | RED dashboard to import (M3) |
| `k6/smoke.js`, `k6/ramp.js` | Load tests, non-AI endpoints only (M8) |
| `PERF-BASELINE.md` | Baseline + before/after template (M8) |

**Env vars (backend):**

| Var | Effect |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset = OTel off. `http://localhost:4318` (Jaeger) or `https://otlp-gateway-<zone>.grafana.net/otlp` |
| `OTEL_EXPORTER_OTLP_HEADERS` | Grafana Cloud auth: `Authorization=Basic <base64(instanceID:token)>` (their setup UI generates this) |
| `DEPLOYMENT_ENVIRONMENT` | `local` / `production` — resource attribute on every signal |
| `OTEL_METRICS_EXPORT` / `OTEL_LOGS_EXPORT` | set `false` with local Jaeger (traces-only backend); leave unset for Grafana Cloud |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | unset = Langfuse off |
| `LANGFUSE_BASE_URL` | `https://cloud.langfuse.com` |
| `LANGFUSE_TRACING_ENVIRONMENT` | `local` / `production` on Langfuse traces |

---

## M1 — Local trace lab (do this first; no accounts needed)

```bash
# 1. Start Jaeger (Docker Desktop must be running)
cd backend && docker compose -f docker-compose.jaeger.yml up -d

# 2. Point the backend at it — in backend/.env add (Jaeger is traces-only,
#    so switch the other two signals off locally):
#    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
#    OTEL_LOGS_EXPORT=false
#    OTEL_METRICS_EXPORT=false

# 3. Run the backend + frontend as usual, click around the app.
# 4. Open http://localhost:16686 → service "trialreads-api".
```

### Trace-reading exercise (verify coverage yourself)

| Action in the app | Expected span structure in Jaeger |
|---|---|
| Open the library page | `GET /library` → child `SELECT` span (SQLAlchemy) |
| Run a summary | `POST /summarise` → `summarise.generate` → httpx `POST api.openai.com` |
| Ask a library question | `POST /library/query` → `nl_sql.generate_and_execute` (attrs: `app.nl_sql.sql`, `sql_generated`) → OpenAI call + `SELECT` on the RLS engine |
| One curation turn | `POST /shelves/{shelf_id}/curate` → `curate.agent_turn` (attr `app.curate.total_tokens`) → N× httpx OpenAI + `curate.tool.search_google_books` (attr `app.tool.query`) → `curate.extract` → `curate.ground` |
| Any authed request | request span has `app.user_id`, `app.cold_start`, `app.seconds_since_boot` |

**The question this milestone answers:** open one `/curate` trace and read off
how much of the wall time is OpenAI calls vs. everything else. Write it down —
that number is what Phase 3 exists to improve.

---

## M2 — Ship to Grafana Cloud  *(you: ~15 min of account/dashboard work)*

1. Create a free account at grafana.com → your stack → **Connections →
   OpenTelemetry (OTLP)** guided setup. It generates exactly the values we
   consume: `OTEL_EXPORTER_OTLP_ENDPOINT` (ends in `/otlp`) and
   `OTEL_EXPORTER_OTLP_HEADERS` (`Authorization=Basic <base64>`). Follow what
   the UI generates — don't hand-assemble.
2. In **Render → trialreads-backend → Environment**, add those two vars
   (`DEPLOYMENT_ENVIRONMENT=production` is already in render.yaml). Deploy.
3. Local stays on Jaeger (cleaner separation); nothing else changes.

### Verification checklist

- Grafana → Explore → Tempo datasource → search `service.name=trialreads-api`.
- Run one `/curate` turn in the deployed app → find the trace, confirm the
  manual spans from the M1 table appear nested inside the request span.
- Force an error (e.g. malformed `POST /library` body via curl with a valid
  JWT, or temporarily bad SQL question) → the trace shows error status (500s
  are recorded as span errors by the FastAPI instrumentation).
- Confirm `app.user_id` is on the request span; confirm the `deployment.environment=production` resource attribute.

---

## M3 — Metrics + RED dashboard  *(you: import + one alert)*

**Decision, made:** the app emits **explicit OTel metrics** — the FastAPI
instrumentation's `http.server.request.duration` histogram (seconds, stable
HTTP semconv, opted in via `OTEL_SEMCONV_STABILITY_OPT_IN=http` in
telemetry.py). Rationale: works against any backend, no dependence on
Tempo-side span-metrics generation being enabled/free; histogram buckets are
extended to 120 s so the AI endpoints' p95/p99 don't clip (telemetry.py).
Labels are **route template + method + status code only** — the cardinality
lesson is commented in telemetry.py.

1. **First check names in Explore** (translation OTLP→Prometheus): Grafana →
   Explore → Prometheus datasource → metric browser → look for
   `http_server_request_duration_seconds_bucket` and labels `http_route`,
   `http_response_status_code`, `deployment_environment`, `job="trialreads-api"`.
   If names differ slightly, adjust the dashboard JSON accordingly.
2. Dashboards → New → **Import** → upload `observability/grafana-dashboard.json`,
   pick your Prometheus + Tempo datasources.
3. **One alert:** Alerting → Alert rules → New. Query:
   `sum(rate(http_server_request_duration_seconds_count{job="trialreads-api",http_response_status_code=~"5.."}[5m])) / sum(rate(http_server_request_duration_seconds_count{job="trialreads-api"}[5m]))`
   → condition `> 0.05` for `5m` → contact point: your email
   (anaghamulloth@gmail.com — verify the contact point first).
   Test it by temporarily lowering the threshold to `> 0`, triggering one error,
   then restoring.

### Percentile exercise

```bash
for i in $(seq 1 50); do curl -s -o /dev/null https://<render-app>.onrender.com/health & done; wait
```
Watch the `/health` p50 vs p95 panels: the first requests after idle (cold
start) drag p95/p99 up while p50 stays low — percentiles vs. averages in one
picture.

---

## M4 — Logs (already flowing once M2 is done)

Structured JSON logs go to **stdout always** and, when OTLP is configured, via
the **OTel logs pipeline to the same Grafana endpoint → Loki** (chosen because
Render's free tier can't run a sidecar/collector; the OTLP gateway needs none).
Every line carries `trace_id`/`span_id` from the active span.

**Secrets audit (done while converting):** existing log calls log generated
SQL + user_id (nl-sql path) and token counts (curate path). No secrets, JWTs,
or API keys are logged anywhere. Borderline item, decided consciously: the
generated SQL line stays — it's the Phase 1 debugging tool and contains no
credentials (it can reference the user's own library contents).

**Correlation setup (you, in Grafana):** Connections → Data sources → your
Tempo datasource → **Trace to logs** → target the Loki datasource, filter by
tag `service.name`, enable "span start/end time shift" padding (±1m). Then:

1. Run a `/library/query` in prod.
2. Tempo → find the trace → click the "logs for this span" icon → Loki opens
   filtered to that window; the `Generated SQL (user …)` line is there with the
   same `trace_id` in its JSON body.

---

## M5 — Langfuse  *(you: account + keys + one decision)*

**Integration path (checked against current Langfuse docs, July 2026 — SDK v4,
requires Python ≥3.11, we're on 3.12):**

- **LangGraph/LangChain (curate, summarise, recommend): implemented.**
  `langfuse.langchain.CallbackHandler` passed per-invocation with
  `langfuse_user_id` / `langfuse_tags` metadata keys (the docs' recommended
  "simplest approach"). Tags carry the feature name and `otel:<trace_id>` —
  so from a slow Grafana trace, copy the trace id and search Langfuse tags for
  it (Grafana → Langfuse cross-link, manual but reliable).
- **LlamaIndex (nl-sql): deliberately NOT wired yet.** Langfuse's current
  recommendation is OpenInference instrumentation
  (`openinference-instrumentation-llama-index` → `LlamaIndexInstrumentor().instrument()`),
  which registers on the **global OTel tracer provider that Grafana already
  owns** in telemetry.py. Making both coexist (Langfuse spans to Langfuse,
  app spans to Grafana) needs live keys to test. Do this as a follow-up with
  keys in hand; until then nl-sql is still fully visible in Tempo (span
  `nl_sql.generate_and_execute` with the SQL text) — you just don't get its
  token/cost breakdown in Langfuse.

**Setup:** create a Langfuse Cloud Hobby account → project → API keys → set
`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`,
`LANGFUSE_TRACING_ENVIRONMENT=production` in Render (placeholders already in
render.yaml). Redeploy.

**Privacy decision (decide consciously, don't default):** Langfuse stores full
prompts/completions. Curation chats contain users' stated goals; as sole
maintainer this is likely acceptable, but Langfuse has masking options if not —
check "masking" in their docs and write the decision here: ☐ store as-is
☐ masked.

**Verification:** run the consulting-shelf conversation in prod → Langfuse →
Traces: one trace per agent turn (plus a small one for the extraction pass),
steps for each model/tool call, token counts and cost per generation
(gpt-4o-mini is in Langfuse's built-in price list; if cost shows 0, add the
model price under Settings → Models). Answer from data: **what does one average
curation conversation cost?** → record in PERF-BASELINE.md.

**Cap watch:** Settings → Usage — Hobby is ~50k units/month with a hard stop.
Check after the first week; agent turns are multi-unit.

---

## M6 — Vercel Speed Insights  *(done in code; you: one toggle)*

`<SpeedInsights />` is in `frontend/app/layout.tsx` (`@vercel/speed-insights/next`,
Next 14 App Router path per current Vercel docs). It's production-only by
design and adds no meaningful bundle weight (async script).

**You:** Vercel dashboard → project → **Speed Insights tab → Enable** (data
collection starts only after this + a new deploy). Free tier: check the shown
data-point limit while you're there. After a few days, find your worst
page/metric pair. Thresholds ("good"): **LCP ≤ 2.5 s · INP ≤ 200 ms ·
CLS ≤ 0.1** (field data, p75).

---

## M7 — Synthetics + cold starts  *(code done; you: configure probes)*

Code side shipped: `/health` returns `{status, version, uptime_seconds}`
(version = Render git commit; no auth/DB/OpenAI), and every request span gets
`app.cold_start` + `app.seconds_since_boot` (see telemetry.py) — the dashboard's
cold-start panel and Tempo filters (`span.app.cold_start=true`) use these.

**You, in Grafana Cloud:** Testing & synthetics → Synthetic Monitoring →
Add check → **HTTP** →
- `https://<render-app>.onrender.com/health`, and a second check for the
  Vercel frontend URL;
- probe region near your Render region;
- assertion: status 200;
- alert on N consecutive failures → email contact point;
- test the alert once by pointing a temporary check at `/nonexistent`.

**Probe interval — a real decision:** Render free tier spins down after ~15 min
idle. A probe every 5 min keeps the instance permanently warm (masking real
cold-start behaviour and using instance hours ~24/7); every 15+ min lets it
sleep (honest cold-start data, users pay the spin-up). Check Render's current
free-tier terms, pick, and **document the choice here:** ☐ 5 min (warm)
☐ 15 min (honest). After a few days, fill the cold-start numbers in
PERF-BASELINE.md from the dashboard.

---

## M8 — Baseline → load test → one improvement

1. Fill `PERF-BASELINE.md` from the dashboards (exclude cold starts).
2. `k6 run k6/smoke.js` then `k6/ramp.js` against prod with a **dedicated test
   account's JWT** in `TR_JWT` (get one by logging in as the test user and
   copying the Supabase access token). Never point k6 at the AI endpoints —
   the scripts don't, keep it that way.
   To run from Grafana Cloud k6 instead (results stored next to your
   dashboards): Performance testing → create test → upload the script → set
   `TR_JWT`/`TR_BASE_URL` as environment variables in the test settings. Free
   tier includes 500 virtual-user hours — the ramp uses well under 1.
3. Pick ONE improvement the data points at, implement, redeploy, re-run the
   identical script, record before/after in PERF-BASELINE.md.

---

## Free-tier caps (verified July 2026 — re-check at signup)

- Grafana Cloud: ~10k metric series / 50 GB traces / 50 GB logs / month,
  14-day retention, Synthetics allowance is large, k6: 500 VUh.
- Langfuse Hobby: ~50k units/month, 30-day retention, **hard stop**.
- At current traffic all of these are far away; the low-cardinality label
  design keeps it that way.
