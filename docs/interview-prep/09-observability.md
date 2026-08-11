# 09 — Observability (Telemetry, Logging, Monitoring)

> A senior differentiator. Most portfolio apps have `print()` and nothing else;
> TrialReads has a real OpenTelemetry pipeline with correct cardinality discipline —
> exactly the maturity signal L5 interviewers look for.

## 1. The concept

Observability is the ability to understand a system's internal state from its outputs,
*especially* to debug problems you didn't anticipate. The **three pillars**:

- **Metrics** — cheap, aggregated numbers over time (request rate, error rate, latency
  percentiles). Great for dashboards and alerts; **bounded cardinality** is critical.
- **Traces** — the path of one request across components, as a tree of timed **spans**.
  Great for "why was *this* request slow?"
- **Logs** — timestamped events with detail. Great for "what exactly happened here?"

Cross-cutting concepts: **RED** (Rate, Errors, Duration — the three golden signals for a
request-driven service) and **USE** (Utilization, Saturation, Errors for resources);
**cardinality** (the number of distinct label combinations — high-cardinality labels on
*metrics* explode cost and query latency, so identifiers belong on traces/logs, not metric
labels); **correlation** (join a metric spike → a trace → its logs); **SLI/SLO/SLA**;
**structured logging**; and the distinction between **monitoring** (known dashboards/alerts)
and **observability** (asking new questions of your data).

## 2. In TrialReads

All telemetry lives in one module, `backend/app/telemetry.py`, exporting over **OTLP** to a
backend chosen purely by env var (local Jaeger or Grafana Cloud → Tempo/Mimir/Loki). It's a
**no-op unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set**, so it costs nothing locally.

**Traces.** Auto-instrumentation for FastAPI (a server span per request), SQLAlchemy (every
query, on *both* the pooled engine and the per-request RLS engines), and httpx (the OpenAI
SDK's transport + Google Books/Hardcover calls). Plus **manual spans** where auto-spans
can't see intent — `nl_sql.generate_and_execute` groups "generate SQL → execute it" into one
unit of work; `curate.agent_turn`, `curate.ground`, and per-item grounding spans capture the
agent's shape. Manual spans carry rich attributes (`app.nl_sql.sql`, `app.curate.total_tokens`,
`app.book`, `app.verified`).

**Metrics with deliberate cardinality discipline** (the part that shows real maturity). The
FastAPI instrumentation emits the **RED** histogram `http.server.request.duration`, labeled
by **route *template*** (`http.route = "/shelves/{shelf_id}"`), method, and status code —
a small, fixed label set, so metric cardinality stays tiny. The comments spell out the trap:
raw paths or `user_id` as metric labels would create one time series per distinct value —
unbounded growth that blows up cost and query latency. So **`user_id` is a *span attribute*
only** (set in `auth.py`), never a metric label. The default histogram buckets stop at 10s,
which would clip the AI endpoints' p95/p99 into `+Inf`, so a custom `View` extends the bucket
ladder to 120s.

**Logs** are **structured JSON**, one object per line (`JsonLogFormatter`), and each line
carries the active `trace_id`/`span_id` — so any log joins to its trace in Tempo, and Grafana's
trace-to-logs correlation works both ways. Logging is always on (Render captures stdout as
searchable JSON) even when OTLP export is off; when on, logs also ship to Loki via OTLP — with
a filter that drops the OTel SDK's own logs to avoid an export-fails→logs-error→export-fails
feedback loop.

**Cold-start visibility** (Render free-tier specific). A request hook tags the first span
after boot with `app.cold_start=true` and `app.seconds_since_boot`, so a 40s cold-start
request can be *isolated or excluded* from latency percentiles instead of silently poisoning
them. `/health` also returns `uptime_seconds` and `otel_enabled` so you can tell from the
public endpoint whether the deployed process is exporting.

**Error monitoring & LLM tracing are complementary, not duplicated.** Sentry owns
error/exception *alerting*; OpenTelemetry owns *performance* investigation; Langfuse owns
*LLM-specific* tracing (prompts/tokens), cross-linked to the OTel `trace_id` (section 08).
The frontend also runs Sentry + Vercel Speed Insights (Core Web Vitals).

## 3. Gaps & upgrades to industry standard

- **No alerts / SLOs defined.** The signals exist but there are no alert rules ("error rate
  > 2% for 5m", "p95 > Xs") or documented SLOs/error budgets. That's the difference between
  *observable* and *operated*.
- **100% trace sampling** (`traces_sample_rate` on Sentry is 0.1, but OTel spans aren't
  head-sampled). At volume you'd tail-sample (keep all errors/slow traces, sample the rest)
  to control cost.
- **No RUM correlation end-to-end.** Frontend (Speed Insights/Sentry) and backend (OTel)
  aren't trace-linked, so you can't follow one user action browser→DB in a single trace.
  Propagating a trace header from the frontend would close this.
- **No dashboards-as-code.** Dashboards are built in Grafana's UI, not versioned (Jsonnet/
  Terraform) — so they're not reproducible or reviewed.
- **LlamaIndex path isn't in Langfuse yet** (needs OpenInference instrumentation, noted in
  the code) — so text-to-SQL LLM calls are traced in OTel but not cost-attributed in Langfuse.
- **Business metrics missing.** RED covers system health; there are no product metrics
  (shelves created, agent-accept rate, books-per-list) to tie engineering to outcomes.

## 4. Ten interview questions & answers (framed around TrialReads)

**Q1. What are the three pillars of observability and how does your app use each?**
A: Metrics — the RED request histogram (rate/errors/duration) labeled by route template, for
dashboards/alerts. Traces — a span tree per request (FastAPI, SQLAlchemy, httpx auto-spans
plus manual spans grouping the LLM+DB "unit of work"), for "why was this request slow?"
Logs — structured JSON carrying the trace id, for "what exactly happened?" All three export
over OTLP to Grafana Cloud.

**Q2. What's cardinality and why did you keep `user_id` off your metrics?**
A: Cardinality is the number of distinct label combinations. Each unique combination is a
separate time series in the metrics store, so a high-cardinality label like `user_id` or a
raw path creates millions of series — exploding storage cost and query latency, and it's how
metrics bills blow up. So I label metrics only by route *template*, method, and status (a
tiny fixed set), and put `user_id` on the trace span instead, where high cardinality is fine.

**Q3. What is RED and why is it the right model here?**
A: Rate, Errors, Duration — the three golden signals for a request-driven service. My
FastAPI instrumentation emits exactly this histogram per route, so I can dashboard request
rate, error rate, and latency percentiles per endpoint. USE (utilization/saturation/errors)
is the complementary model for resources like the DB pool.

**Q4. Why manual spans if you already have auto-instrumentation?**
A: Auto-instrumentation sees "an OpenAI call" and "a DB query" but not that together they
form one logical operation — generate SQL then execute it. A manual span
(`nl_sql.generate_and_execute`) groups them so the trace shows the unit of work and I can
attach domain attributes like the generated SQL and token count. Auto-spans give breadth;
manual spans give intent.

**Q5. Your AI endpoints take 10–60s. Did that break your metrics?**
A: It would have — the default OpenTelemetry latency histogram tops out at 10s, so anything
slower gets clipped into the +Inf bucket and p95/p99 become meaningless. I added a custom
`View` extending the bucket ladder to 120s so the AI endpoints' tail latency is measured
accurately.

**Q6. How do you connect a metric spike to the actual failing request?**
A: Correlation. A latency spike on a route in Grafana → open exemplar/traces for that route in
Tempo → the slow trace's spans show where the time went → each log line carries the same
trace id, so I jump straight to its logs in Loki. For LLM calls I also stamp the trace id into
Langfuse, so I can see the exact prompts and tokens. One id threads metric→trace→log→LLM.

**Q7. Render's free tier cold-starts. How do you keep that from lying in your dashboards?**
A: The first request after boot is tagged `app.cold_start=true` with `seconds_since_boot`, so
in the dashboard I can exclude or separately chart cold-start requests instead of letting a
40s wake pollute the p95 for every endpoint. `/health` also exposes `uptime_seconds` so a
synthetic monitor can see spin-downs directly.

**Q8. Why keep Sentry, OpenTelemetry, and Langfuse instead of consolidating?**
A: They answer different questions. Sentry is best-in-class for exception grouping and
*alerting on errors*. OpenTelemetry is for *performance* — traces and RED metrics across the
whole request. Langfuse is *LLM-specific* — prompts, tokens, and per-feature cost. They're
cross-linked by trace id, so it's one investigation, not three silos. Consolidating would
lose the specialized strengths.

**Q9. Your telemetry is a no-op without env vars. Why design it that way?**
A: Zero cost and zero risk when unconfigured — no providers installed, manual spans become
free no-ops, only stdout JSON logging remains. So local dev and CI don't need a telemetry
backend, and turning on Grafana Cloud is a pure config change (set the OTLP endpoint +
headers), not a code change. It also means observability can't accidentally add latency to a
request when it's off.

**Q10. What's missing to call this production-*operated*, not just observable?**
A: Alerts and SLOs. I have the signals but no alert rules or error budgets — I'd define SLOs
(e.g., 99% of non-cold reads < 500ms), alert on error rate and latency burn, tail-sample
traces to control cost at volume, version dashboards as code, and add product metrics
(agent-accept rate, shelves created) so engineering ties to outcomes.

---

### Follow-ups interviewers love here
- "Logs vs traces vs metrics — when reach for which?" → metrics to *notice* (alert), traces
  to *localize* (which span), logs to *explain* (what exactly).
- "How would you sample?" → tail-based: keep all errors and slow traces, probabilistically
  sample the fast/successful ones.
- "SLI vs SLO vs SLA?" → SLI is the measured number, SLO your internal target, SLA the
  contractual promise with consequences.
