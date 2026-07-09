# TrialReads eval harness (Phase 4)

Offline evaluation of the AI features. **M1 is Langfuse-free** — it runs golden
datasets over a fixed fixture library and scores answers with a deterministic
check + an LLM-as-judge, writing a Markdown report. Only OpenAI + Supabase
(already in `backend/.env`) are needed. M2 layers Langfuse on top.

## What you'll learn (M1)
- **Golden-dataset design:** answers are deterministic only because the fixture
  (`fixtures/library_fixture.json`) and the dataset (`datasets/nl_sql.jsonl`)
  are kept in lockstep. Change one → update the other.
- **LLM-as-judge:** an NL answer ("You've finished 6 books.") can't be string-matched
  against `"6"`, so a strict judge (`judges.py`) decides semantic correctness.
- **Structural vs semantic checks:** `sql_required` (deterministic) and the judge
  verdict must *both* pass for an item to pass.

## One-time setup
1. **Create a throwaway eval account.** Sign up a test user in the app, then copy
   its UUID from the Supabase dashboard → Authentication → Users.
2. **Add it to `backend/.env`:**
   ```
   EVAL_USER_ID=<that-uuid>
   ```
   (The FK `library.user_id → auth.users(id)` means the fixture user must be a
   real auth user. Use a throwaway — seeding **wipes** its library.)
3. **Seed the fixture:**
   ```
   cd backend
   python -m evals.seed_fixture          # add --force if the user already has rows
   ```

## Run
```
cd backend
python -m evals.run_eval
```
Prints per-item PASS/FAIL, writes `evals/reports/nl_sql.md`, and exits non-zero
if the pass rate is below `EVAL_PASS_THRESHOLD` (default 0.8) — CI-gate ready.

## Config (all optional, from `.env` / env)
| Var | Default | Meaning |
|-----|---------|---------|
| `EVAL_USER_ID` | — (required) | Fixture user's auth UUID |
| `EVAL_JUDGE_MODEL` | `gpt-4o-mini` | Judge model |
| `EVAL_PASS_THRESHOLD` | `0.8` | Min pass rate for exit 0 |

## Layout
```
evals/
  fixtures/library_fixture.json   # canonical library rows
  datasets/nl_sql.jsonl           # question → expected answer (matches fixture)
  seed_fixture.py                 # idempotent seed into EVAL_USER_ID's library
  judges.py                       # LLM-as-judge (Verdict: correct/score/rationale)
  run_eval.py                     # runner → reports/nl_sql.md
  reports/                        # generated
```

## Roadmap
- **M1 (done):** scaffold + NL→SQL, offline.
- **M2:** Langfuse datasets + score recording — hooks into `run_eval.record_result()`,
  the one seam built for it. Needs `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`.
- **M3:** add summaries, recommend, curation — one feature per checkpoint, reusing
  this harness.
