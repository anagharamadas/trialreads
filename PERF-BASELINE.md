# TrialReads — Performance Baseline (Phase 3, M8)

Snapshot of production numbers from the dashboards, plus before/after records
for each improvement loop. Fill from Grafana (RED dashboard, cold starts
excluded via `app.cold_start=false` in Tempo), Langfuse (cost per feature), and
Vercel Speed Insights. Update the date whenever numbers are refreshed.

## Baseline — <YYYY-MM-DD>

### API latency & errors (production, cold starts excluded)

| Endpoint | p50 | p95 | Error rate |
|---|---|---|---|
| GET /health | | | |
| GET /library | | | |
| GET /shelves | | | |
| GET /shelves/{id}/books | | | |
| POST /summarise | | | |
| POST /recommend | | | |
| POST /library/query | | | |
| POST /shelves/{id}/curate | | | |

### Cold starts (Render free tier)

- Cold starts per day: 
- Added latency, worst observed: 
- (From Tempo: search `app.cold_start=true`, compare with warm p50.)

### Load behaviour (k6 ramp.js, identical script for every run)

- Throughput at which p95 degraded: 
- Error onset point (VUs / req/s): 

### AI cost per feature (Langfuse, average per request)

| Feature | Tokens in | Tokens out | Cost |
|---|---|---|---|
| summarise | | | |
| recommend | | | |
| nl-sql | | | |
| curate (per conversation turn) | | | |

### Frontend (Vercel Speed Insights, field data)

- Worst page/metric pair: 
- LCP / INP / CLS on that page: 

---

## Improvement loop #1 — <YYYY-MM-DD>

- **Hypothesis (from which dashboard/panel):**
- **The ONE change made:**
- **Before → after (same k6 script, same panels):**

| Metric | Before | After |
|---|---|---|
| | | |

- **Verdict / kept?**
