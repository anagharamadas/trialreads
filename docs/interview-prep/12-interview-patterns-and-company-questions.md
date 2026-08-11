# 12 — Current Interview Patterns & Company-Specific Questions

> **Honesty note first.** No one can hand you the *verbatim* questions a company will ask —
> banks rotate and reusing leaked questions is against every company's policy. What *is*
> knowable and stable is each company's **loop structure, what each round scores, and the
> representative question *types***. That's what this file gives you, grounded in current
> (2026) interview reports, plus exactly how to steer TrialReads into each round.

## The big 2026 shift: AI-assisted coding rounds

The headline change across FAANG this year is **AI in the room**, and it plays directly to
your strength (you *built* an AI-integrated system):

- **Google** is piloting an **AI-assisted coding round** (candidates use Google's Gemini as
  an assistant) that **replaces one of the two onsite coding rounds**; the other stays a
  classic no-AI algorithm interview. The scored skill shifts from "produce correct code from
  scratch" to **"produce correct code *with* an AI tool and show judgment about its
  output."**
- **Meta** replaced a blank-whiteboard coding round (E4/E5) with a **multi-file codebase you
  read, debug, and optimize — with an AI tool available**. This rewards real-world skills:
  navigating an unfamiliar codebase, spotting bugs, refactoring.
- **Amazon** reports a **"Gen AI Fluency"** element and a new **20-minute system-design
  sketch in the OA** for SDE-II+.

**Why this matters for you:** the industry is explicitly moving from "invert a binary tree on
a whiteboard" toward **engineering judgment, reading/debugging existing systems, and working
with AI** — which is exactly what shipping TrialReads (an LLM agent, a real codebase, real
incidents debugged) demonstrates. Lean into it.

## Company-by-company (current loops + how TrialReads maps in)

### Google (L3–L5)
- **Loop:** recruiter screen → phone screen (1 coding) → onsite of ~4–5: **two coding**
  (one may be the AI-assisted format), **system design** (L5+; L4 sometimes), and
  **"Googleyness & Leadership"** (behavioral). A **hiring committee** (not the interviewers)
  makes the call from written feedback — so *how clearly you communicate* is scored, not just
  the answer.
- **Scores:** general cognitive ability, coding (data structures/algorithms, clean code,
  complexity), system design (for senior), and Googleyness (collaboration, ambiguity).
- **Representative *types*:** graph/tree/DP/hashing coding; "design a URL shortener / a
  web crawler / YouTube"; "tell me about a time you dealt with ambiguity."
- **TrialReads angle:** your system-design and behavioral rounds. When they say "design a
  multi-tenant app with per-user data isolation," you have a *shipped* answer (RLS +
  defense-in-depth, section 05). For the AI-assisted round, you're comfortable reasoning about
  an LLM's output because you built guardrails around one.

### Amazon (SDE-I / SDE-II)
- **Loop:** OA (coding + now a **20-min system-design sketch** for SDE-II+, e.g. "design a
  package-tracking system") → onsite of 4–5: **2–3 DSA**, **1 system design**, **hiring
  manager**, and **1 Bar Raiser**.
- **The Amazon-specific thing — Leadership Principles.** Amazon weights the **14 LPs** as
  heavily as coding. *Every* round, especially the **Bar Raiser** (a senior interviewer from
  another team guarding the hiring bar), digs into behavioral stories mapped to LPs
  (Customer Obsession, Ownership, Dive Deep, Bias for Action, Deliver Results, Are Right A
  Lot, Invent and Simplify). Prep **STAR** stories as hard as DSA. Note their coding culture:
  **working code beats optimal-but-buggy** — get it correct, then optimize.
- **TrialReads angle:** a goldmine for LP stories (see the story bank below). "Dive Deep" =
  the ES256/JWKS auth discovery; "Bias for Action" = shipping the RLS isolation before any
  app code; "Customer Obsession" = the grounding rule so users never see a fake book;
  "Are Right, A Lot / Deliver Results" = the CORS incident diagnosis.

### Meta / Facebook (E3–E5)
- **Loop:** phone screen → onsite: **2 coding** ("Ninja" — usually 2 medium problems in ~45
  min, so speed matters; and/or the new **codebase debug+optimize with AI**), **system
  design** ("product architecture" — design News Feed / Instagram / Messenger, emphasis on
  data model + API + scale), and **behavioral ("Jedi")** — cross-functional collaboration,
  conflict, driving projects.
- **Scores:** coding speed + correctness, product-flavored system design, and "did you drive
  impact / work well with others."
- **TrialReads angle:** the product-architecture round loves a real product you designed
  end-to-end. You can whiteboard TrialReads' data model, API, and the read/write paths, then
  extend it ("now add social sharing of shelves" → new table + RLS policy + N+1 considerations
  you already reason about).

### Flipkart (SDE-1 / SDE-2) — and Indian product companies broadly
- **Loop (4–5 rounds over ~3–4 weeks):** OA → **DSA** live round → **Machine Coding round**
  → **system design** (SDE-2+) → **managerial + HR**.
- **The defining differentiator — the Machine Coding round.** ~90–120 minutes to build a
  **small, runnable, well-designed program** from a real-world prompt (parking lot, expense
  splitter/Splitwise, a rate limiter, an in-memory cache, a snake-and-ladder game). It scores
  **object-oriented / low-level design, clean extensible code, working output, and edge-case
  handling — NOT algorithms.** DSA-only preppers famously struggle here.
- **TrialReads angle:** this is where having *designed classes and clear boundaries* pays off.
  Practice by re-implementing a TrialReads slice as a standalone LLD exercise: "design an
  in-memory shelves service with add/reorder/dedup" exercises the exact skills (SOLID,
  interfaces, the `reading_order` reorder, the dedup rule). Your rate limiter, cache, and
  API design are all machine-coding-shaped.
- *(Companies like Uber, Swiggy, Zomato, PhonePe, Atlassian, and many others run a very
  similar machine-coding / LLD round — this prep generalizes across the Indian product
  ecosystem.)*

## The four round *types*, and how to win each with TrialReads

Every company's loop is a mix of these four. Map your prep to the **type**, not the company.

**1. Coding / DSA (+ AI-assisted variants).** TrialReads doesn't teach this — LeetCode does
(you've got it). For the *AI-assisted / codebase-debug* variants, your edge is real: you've
read and reasoned about unfamiliar code and worked with an LLM as a tool. Practice narrating
your judgment ("I'd verify the AI's output against this edge case").

**2. System Design.** Your strongest transferable asset. Have a crisp 5-minute TrialReads
architecture pitch (section 01) and be ready to *extend* it live: add caching, make the agent
async with a queue, shard by tenant, add read replicas. Practice the standard prompts (URL
shortener, News Feed, rate limiter, a chat app) but anchor answers in patterns you've *shipped*
— statelessness, RLS isolation, RED metrics, rate limiting.

**3. Low-Level Design / Machine Coding.** Flipkart-style. Practice building runnable OOP from
a prompt in 90 min. Reuse TrialReads slices as exercises (rate limiter, shelves service, an
LRU cover cache). Emphasize interfaces, SOLID, extensibility, and edge cases (empty, duplicate,
concurrent).

**4. Behavioral.** Amazon LPs, Meta Jedi, Google Googleyness. This is where a *real project
with real incidents* crushes generic answers. Build a STAR story bank from TrialReads:

## Your TrialReads behavioral story bank (STAR-ready)

| Real incident (in this repo) | Maps to | The story in one line |
|---|---|---|
| Discovered Supabase issued **ES256/JWKS**, not HS256; auth silently rejected real tokens | *Dive Deep* (Amazon), debugging, ambiguity | Inspected a live token's header, found the alg mismatch, switched to JWKS verification with caching. |
| **CORS** blocked all API calls when Next.js auto-bumped the port; app looked "crashed" | *Are Right A Lot / customer impact*, root-causing | Read the preflight in the network tab, saw the 400, fixed to allow any localhost port in dev + lock to Vercel in prod. |
| Made **tenant isolation** provably correct **before** building app code | *Bias for Action / Ownership*, security mindset | Wrote adversarial two-account tests at the DB layer first; only then built on top. |
| **Grounding** rule: no book reaches the user unless Google Books confirms it | *Customer Obsession / Insist on Highest Standards* | Refused to let the LLM hallucinate; enforced verification in code, not just the prompt. |
| Vercel **silently blocked deploys** on a commit-email mismatch | *Diagnose, don't guess* | Checked the Deployments tab, found the blocked reason, fixed the git author email. |
| "Covers show as **anime**" — turned out to be a browser extension | *Deal with ambiguity / dive deep* | Proved the data+code were correct in a clean browser before touching code. |
| Cut agent grounding from **~15s → ~3s** with bounded parallelism | *Deliver Results / think big* | Fanned lookups across a 6-worker pool, preserved order, kept the trace context intact. |
| Built **observability** (OTel RED metrics, cardinality discipline) most portfolios skip | *Insist on Highest Standards / ownership* | Treated it like production: cardinality-safe labels, cold-start tagging, trace-log correlation. |

Practice each in **STAR** (Situation, Task, Action, Result) with a metric in the Result.

## How to steer any interview toward your strengths

- In **system design**, when given a generic prompt, say "I recently built a multi-tenant app
  with exactly this isolation problem — here's how I solved it" and bring in RLS,
  statelessness, rate limiting, and observability. You're translating shipped experience, not
  reciting a blog.
- In **behavioral**, default to TrialReads incidents — they're concrete, they have metrics,
  and they show judgment under real constraints.
- In **AI-assisted / AI-fluency** rounds, you have a genuine edge: you've built with an LLM,
  grounded it, observed it, and rate-limited it. Talk about *engineering judgment over model
  output* — that's precisely the new scored skill.

---

### A note on "grinding" vs. this doc
DSA/coding rounds still gate the pipeline at every company — keep grinding those (your call,
and you've got it). **This documentation is your edge in the other three round types
(system design, LLD/machine-coding, behavioral)**, which is where most candidates are weak and
where a real, well-engineered, well-observed system speaks far louder than memorized answers.

## Sources (current 2026 interview reports)
- [Google's AI-Assisted Coding Interview (2026 Guide) — Exponent](https://www.tryexponent.com/blog/google-ai-coding-interview)
- [Inside the Google 2026 Loop: Rounds & Rubric](https://dglearning.substack.com/p/inside-the-google-2026-loop-rounds)
- [Meta Interview Process 2026: Rounds, AI-Assisted Coding & Behavioral](https://claveprep.com/blog/meta-interview-process-2026-guide)
- [FAANG Interview Loops Decoded 2026 — Wrok](https://www.wrok.app/blog/faang-interview-loops-2026)
- [Amazon SDE Interview 2026: New Loop Format & Leadership Principles — Topalupu](https://www.topalupu.com/blog/amazon-sde-interview-2026)
- [Amazon Interview Process 2026: Leadership Principles, Loop & Bar Raiser — Ophy](https://ophyai.com/blog/company-guides/amazon-interview-guide)
- [Flipkart Interview Process 2026: Machine Coding, DSA & Timeline — Ophy](https://ophyai.com/blog/company-guides/flipkart-interview-guide)
- [Machine Coding Round: Flipkart SDE-II Interview — Medium](https://medium.com/@shbhggrwl/%EF%B8%8F-machine-coding-round-flipkart-sde-ii-interview-f8b9475330c4)
