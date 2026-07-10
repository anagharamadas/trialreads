"""TrialReads evaluation harness (Phase 4).

M1 (this milestone) is deliberately Langfuse-free: it runs golden datasets over a
fixed fixture library, scores each answer with a deterministic check plus an
LLM-as-judge, and writes a Markdown report to evals/reports/. No external
account is required — only OPENAI_API_KEY (already in backend/.env) and a
throwaway EVAL_USER_ID whose library holds the fixture.

M2 will add Langfuse datasets + score recording without changing the harness
shape: run_eval already funnels every result through record_result(), the single
seam where a Langfuse sink slots in.
"""
