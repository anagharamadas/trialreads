# TrialReads — Interview Preparation Documentation

A concept-by-concept diagnosis of the **deployed** TrialReads system, written to
double as SWE-interview preparation for MAANG-tier roles. Every section is
grounded in the actual code in this repo (files/lines are cited so you can point
an interviewer straight at the implementation).

## How to use this

Each concept has its own file with four parts:

1. **The concept** — a high-level, framework-agnostic explanation of the idea as a
   software engineer must be able to articulate it.
2. **In TrialReads** — exactly how it's implemented here, with file references and
   the *reasoning* behind each decision (the "why", which is what senior interviews
   probe).
3. **Gaps & upgrades to industry standard** — an honest list of what's missing or
   simplified versus what a large-scale production system would do, so you can
   answer "how would you improve this?" credibly.
4. **10 interview questions & answers** — questions an interviewer would ask *about
   this concept, framed around TrialReads*, with model answers you can actually say
   out loud (tight, structured, follow-up-aware).

A final file covers **current interview patterns and representative questions** at
Google, Amazon, Meta, Flipkart, etc., and how to steer TrialReads into those rounds.

## The system in one paragraph (for context)

TrialReads is a multi-tenant, full-stack reading app: a **Next.js** (App Router)
frontend on **Vercel**, a stateless **FastAPI** backend on **Render**, and
**Supabase Postgres** (+ Supabase Auth) as the data/identity layer. It has three
LLM features (chapter summaries, recommendations, and natural-language "text-to-SQL"
over your library) plus a **LangGraph curation agent** that builds ordered reading
lists grounded in the Google Books API. Cross-cutting: JWT (ES256/JWKS) auth,
Postgres **Row-Level Security** for tenant isolation, per-user rate limiting,
**OpenTelemetry** traces/metrics/logs, and Sentry.

## Concept sections

| # | Concept | Interview weight | Status in repo |
|---|---|---|---|
| [01](01-system-architecture-and-design.md) | System architecture & design | High (all levels) | ✅ written |
| [02](02-databases-and-data-modeling.md) | Relational databases & data modeling | High | ✅ written |
| [03](03-rest-api-design.md) | REST API design | High | ✅ written |
| [04](04-authentication-jwt-jwks.md) | Authentication (JWT / JWKS) | Medium–High | ✅ written |
| [05](05-authorization-and-multitenant-security.md) | Authorization & multi-tenant security (RLS) | High | ✅ written |
| [06](06-concurrency-async-connections.md) | Concurrency, async & connection management | Medium–High | ✅ written |
| [07](07-rate-limiting-and-resilience.md) | Rate limiting & resilience | Medium | ✅ written |
| [08](08-llm-ai-engineering.md) | LLM / AI engineering (agent, grounding, memory) | High (AI roles) | ✅ written |
| [09](09-observability.md) | Observability (OpenTelemetry, logs, Sentry) | Medium–High (senior) | ✅ written |
| [10](10-cicd-and-deployment.md) | CI/CD & deployment (IaC, 12-factor) | Medium | ✅ written |
| [11](11-frontend-engineering.md) | Frontend engineering (Next.js, React) | Medium | ✅ written |
| [12](12-interview-patterns-and-company-questions.md) | Current interview patterns & company-specific questions | — | ✅ written |

All 12 sections are complete. Each concept section follows the four-part format above;
section 12 covers current (2026) company loops and how to steer TrialReads into each round.

## Levels (so you can calibrate depth)

- **L3 / new-grad:** DSA dominates (not covered here — you're handling that). Of the
  above, expect basic API, DB, and "explain your project" depth.
- **L4 / SDE-II:** API design, data modeling, concurrency, testing, and a light
  system-design round carry real weight. **This is the sweet spot TrialReads
  demonstrates.**
- **L5+ / senior:** system-design depth, distributed-systems trade-offs, reliability,
  observability, and crisp trade-off communication are the differentiators — sections
  01, 05, 06, 09 are your strongest senior signal here.
