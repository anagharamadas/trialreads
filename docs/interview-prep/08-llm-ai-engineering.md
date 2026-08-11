# 08 — LLM / AI Engineering

> Increasingly its own interview loop ("AI/ML engineer," "GenAI"). TrialReads has four
> distinct LLM features and a real agent, so it's strong material — the theme
> interviewers care about is **making a non-deterministic model behave like a reliable
> component**.

## 1. The concept

Building *with* LLMs (not training them) is a systems problem: the model is a
non-deterministic, occasionally-wrong, latency-and-cost-heavy dependency you must wrap in
guardrails. Core ideas:

- **Prompt engineering** — system prompts that pin role, constraints, and output format;
  temperature (creativity vs. determinism).
- **Grounding / RAG** — tie outputs to a trusted source so the model can't hallucinate
  facts; retrieval-augmented generation and tool use are two flavors.
- **Tool use / function calling / agents** — the model decides to call tools (search, DB,
  APIs); a **ReAct** agent loops reason→act→observe until done.
- **Structured output** — forcing the model to emit a schema (JSON/function args) instead
  of prose you must parse.
- **Hallucination control & evaluation** — how you *know* it's right; grounding,
  validation, and evals.
- **Memory** — LLMs are stateless per call; multi-turn needs history management (send it
  all, summarize it, or the **condense-question** pattern).
- **Cost/latency** — token budgets, model choice, caching, parallelism, and observability.

## 2. In TrialReads

Four LLM features, each with a different guardrail strategy — that variety is the point.

### The curation agent (`services/curation_agent.py`) — the headline

A **LangGraph ReAct agent** (`create_react_agent`) with a single tool,
`search_google_books`. The design is a deliberate **two-stage** split, chosen after
`gpt-4o-mini` proved unreliable at emitting a nested tool call for the final list:

1. **Stage 1 — research/converse.** The agent asks 2–4 clarifying questions when the goal
   is vague, then researches via the search tool, then presents a list *as prose*. Its
   system prompt (`RESEARCH_PROMPT`) pins the behavior: clarify first; recommend **only**
   books returned by the tool; books only, no magazines; **never more than 10** even if
   asked; propose fewer honestly if few exist.
2. **Stage 2 — structured extraction.** A separate call uses
   `with_structured_output(_Extracted)` to reliably pull the ordered list out of the
   agent's prose into a Pydantic schema — far more dependable than trusting the small model
   to produce a nested function call.

**Grounding by construction — the anti-hallucination core.** Every extracted book is
re-validated against Google Books (`_ground` → `_ground_one`): if Google Books can't
confirm it, it's **dropped**; author-less results (likely magazines) are dropped; the cover
and canonical title/author come from the *validated* record, and the rating from Hardcover.
So **no invented book can survive to the user** — grounding is enforced in code, not just
requested in the prompt. That's the difference between "please don't hallucinate" and
"you *cannot* hallucinate."

**The agent never writes to the DB.** It proposes; the user accepts; only then does the
separate bulk endpoint write (`added_by='agent'`). The LLM is kept entirely out of the
write path — the same defense-in-depth instinct as the text-to-SQL sandbox.

### Text-to-SQL with memory (`services/library_query.py`)

Natural language → SQL over the user's library via LlamaIndex `NLSQLTableQueryEngine`.
Two engineering ideas:
- **Grounding via schema context** — a `TABLE_CONTEXT` string teaches the model the exact
  columns and semantics (e.g., `status='Finished' AND year=<y>` for "read in <year>"), so
  generated SQL matches the data model.
- **Memory via the condense-question pattern** — the engine answers one self-contained
  question, so a follow-up ("and in 2024?") is first *rewritten* into a standalone question
  using the last N turns (`_condense`), then answered. This is the classic conversational-
  retrieval pattern, and it keeps the backend stateless (history comes from the client).
- Security is enforced at the DB, not the prompt (section 05).

### Summaries & recommendations

Simpler prompt-chain features (`summariser.py`, `recommendations.py`) — the recommendation
parser is format-coupled to a fixed prompt, an example of the fragility that motivated the
structured-output approach in the agent.

### LLM observability (`llm_observability.py`)

**Langfuse** traces every LLM run, tagged by feature (`summarise`/`nl-sql`/`curate`/
`recommend`) so cost and latency can be answered *per feature*, and cross-linked to the
OpenTelemetry `trace_id` so a slow trace in Grafana can be opened in Langfuse. It's a
no-op without keys, and the callback import is guarded so monitoring can never break a paid
request. Token usage is also logged per curate turn.

## 3. Gaps & upgrades to industry standard

- **No evaluation harness.** Correctness is verified by manual spot-checks. Production LLM
  systems have an **eval suite** (golden Q→SQL pairs; agent proposals scored for
  relevance/grounding) run in CI so a prompt tweak can't silently regress quality.
- **No response caching.** Identical summaries/queries re-hit OpenAI. Cache keyed on
  (feature, normalized input) would cut cost and latency dramatically.
- **No streaming.** The agent's answer arrives all at once after 10–60s; token streaming
  (SSE) would make it feel instant.
- **No prompt-injection defense on the *conversational* surface.** The text-to-SQL path is
  DB-sandboxed, but a user could try to jailbreak the agent's persona; harmless here (it
  only reads Google Books), but a system that took actions would need input/output
  guardrails.
- **Single provider, hard-coded model.** `gpt-4o-mini` is inline; an abstraction (and a
  cheaper/faster model per feature) would cut cost and avoid vendor lock-in.
- **Synchronous** — see section 01; long agent runs should be queued/streamed.
- **Fixed retrieval depth / no reranking** in text-to-SQL and search; fine here, but RAG at
  scale wants reranking and better retrieval.

## 4. Ten interview questions & answers (framed around TrialReads)

**Q1. Your agent recommends books. How do you guarantee it doesn't invent titles?**
A: Grounding by construction. The prompt says "only books the search tool returned," but I
don't trust the prompt for correctness — after the model proposes a list, I re-validate
every book against Google Books in code. Anything it can't confirm is dropped, and the
cover/author come from the validated record. So a hallucinated book physically can't reach
the user; the guarantee is enforced, not requested.

**Q2. Why the two-stage (agent + separate extraction) design instead of one call?**
A: Reliability with a small model. I first had the agent emit the final list as a
structured tool call, but `gpt-4o-mini` frequently wrote prose instead. So I let it
converse/research freely in stage 1, then use a dedicated `with_structured_output` call in
stage 2 to reliably extract the ordered list into a schema. Separating "reason" from
"format the result" made it robust.

**Q3. What is a ReAct agent and what does yours actually do?**
A: ReAct = Reason + Act: the model loops — think, call a tool, observe the result, repeat —
until it can answer. Mine has one tool, `search_google_books`. It reasons about the user's
goal, searches for candidates, and (when confident) presents a list. I cap the loop with a
recursion limit so it can't spin forever.

**Q4. How do you handle multi-turn conversation if the backend is stateless?**
A: For the agent, the client sends the full history each turn (capped to the last 20). For
text-to-SQL, the query engine answers one self-contained question, so I use the
condense-question pattern: rewrite the follow-up ("and in 2024?") into a standalone
question using the last N turns, then answer that. History lives on the client, so any
backend instance can serve any turn.

**Q5. Temperature — what did you set and why?**
A: 0 for anything that must be deterministic/correct — the SQL generation, the extraction
pass, the condense step. ~0.2 for the agent's conversation, where a little variation makes
recommendations feel less canned but still stays grounded. The grounding step makes
correctness independent of temperature anyway.

**Q6. How do you control the cost of these features?**
A: Per-user daily rate limits (section 07) + an OpenAI account spend cap; a small model
(`gpt-4o-mini`); token logging per turn; and Langfuse tracing tagged per feature so I can
see *which* feature costs what. The obvious next win is caching identical summaries/queries,
which today re-hit the API.

**Q7. How do you know the agent is actually good? How would you evaluate it?**
A: Today it's manual spot-checking against Google Books — honest gap. Production-grade is an
eval harness: a golden set of goals with expected properties (are all books real? in a
sensible order? on-topic?), plus Q→SQL golden pairs for text-to-SQL, scored automatically in
CI. Then a prompt change is gated on not regressing the scores. LLM-as-judge can grade
relevance at scale.

**Q8. Walk me through prompt injection risk in your app.**
A: The dangerous surface would be if user text became privileged action. The text-to-SQL
path turns user text into SQL, so I never rely on the prompt for safety — it runs on an
RLS-scoped connection against a self-filtering view, so even a jailbroken query can't leave
the user's rows (section 05). The agent only reads Google Books and never writes to the DB,
so injecting it just wastes a turn. A system that took real actions would need explicit
input/output guardrails.

**Q9. Why grounding via Google Books instead of trusting the model's knowledge?**
A: LLMs confidently produce plausible-but-fake titles and misattributed authors — exactly
the failure users would notice. Grounding every recommendation in a Google Books lookup
makes the output *verifiable by construction* and, for free, gives me the real cover and
canonical metadata. It converts "trust me" into "here's the source."

**Q10. How do you observe and debug an LLM feature in production?**
A: Langfuse traces every run tagged by feature (summarise/nl-sql/curate/recommend) with
token cost, and I stamp the OpenTelemetry `trace_id` into the Langfuse run — so a slow
request found in Grafana Tempo can be opened directly in Langfuse to see the exact prompts,
tool calls, and tokens. Observability is wrapped so it can never break a user request.

---

### Follow-ups interviewers love here
- "RAG vs. fine-tuning?" → RAG (what I do) grounds in fresh external data and is cheap to
  update; fine-tuning bakes in style/behavior and needs retraining to change facts.
- "What if two users ask the same thing?" → cache on normalized input; today it recomputes.
- "How do you stop the agent looping forever?" → `recursion_limit` on the graph + a bounded
  history window.
