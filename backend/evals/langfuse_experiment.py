"""M2: run the NL->SQL eval as a Langfuse dataset experiment.

Where M1 (`run_eval.py`) scores locally and writes a Markdown report, this pushes
the SAME golden set to a Langfuse **dataset** and runs an **experiment**, so every
run's scores + traces land in the Langfuse UI for comparison over time. It reuses
the M1 assets unchanged: the fixture-seeded `EVAL_USER_ID`, `datasets/nl_sql.jsonl`,
and the LLM judge in `judges.py`.

Design note: M1 promised `record_result()` as the seam for Langfuse. In practice
the v3 SDK's `dataset.run_experiment()` inverts control (it drives the loop and
auto-creates the dataset run, trace links, and dashboard URL) — more robust than
hand-rolling `create_score`, so M2 uses it as a sibling runner rather than a hook
inside M1's loop. The pass/scoring semantics are kept identical to run_eval:
`sql_required` structural check + judge correctness, with `expect_incorrect`
inverting the verdict for the negative control.

    cd backend
    python -m evals.langfuse_experiment

Needs LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY (+ EVAL_USER_ID and a seeded
fixture) in backend/.env.
"""

import sys

from langfuse import Langfuse
from langfuse.experiment import Evaluation

from app import llm_observability
from app.services import library_query

from evals import config, judges, run_eval

DATASET_NAME = "nl-sql-golden"


def sync_dataset(lf: Langfuse, items: list[dict]) -> None:
    """Upsert the golden items into a Langfuse dataset (idempotent via stable id)."""
    lf.create_dataset(
        name=DATASET_NAME,
        description="NL->SQL golden Q&A over the fixture library (TrialReads P4).",
    )
    for it in items:
        lf.create_dataset_item(
            dataset_name=DATASET_NAME,
            id=it["id"],  # stable id → re-running updates rather than duplicates
            input=it["question"],
            expected_output=str(it["expected"]),
            metadata={"checks": it.get("checks", {}), "note": it.get("note")},
        )


def make_task(user_id: str, api_key: str):
    """Task = the real feature. Returns {answer, sql}; the dict becomes the trace
    output, and the manual nl_sql span inside answer_query nests under it."""

    def task(*, item, **kwargs):
        return library_query.answer_query(item.input, user_id, api_key)

    return task


def correctness_evaluator(*, input, output, expected_output=None, metadata=None, **kwargs):
    """Score one item: judge correctness (+ structural sql check) → Langfuse scores.

    Mirrors run_eval.run_item exactly, including the negative-control inversion.
    """
    checks = (metadata or {}).get("checks", {}) if metadata else {}
    answer = output.get("answer", "") if isinstance(output, dict) else str(output or "")
    sql = output.get("sql") if isinstance(output, dict) else None

    verdict = judges.judge_answer(input, expected_output or "", answer)
    evaluations = [
        Evaluation(
            name="correctness",
            value=float(verdict.score),
            comment=verdict.rationale,
            data_type="NUMERIC",
        )
    ]

    sql_ok = True
    if checks.get("sql_required"):
        sql_ok = bool(sql)
        evaluations.append(
            Evaluation(name="sql_generated", value=sql_ok, data_type="BOOLEAN")
        )

    negative_control = bool(checks.get("expect_incorrect"))
    passed = sql_ok and (not verdict.correct if negative_control else verdict.correct)
    evaluations.append(
        Evaluation(
            name="passed",
            value=passed,
            data_type="BOOLEAN",
            comment="negative control (judge must reject)" if negative_control else None,
        )
    )
    return evaluations


def main() -> int:
    if not llm_observability.enabled():
        print(
            "ERROR: Langfuse keys not set. Add LANGFUSE_PUBLIC_KEY / "
            "LANGFUSE_SECRET_KEY to backend/.env.",
            file=sys.stderr,
        )
        return 2
    user_id = config.eval_user_id()
    api_key = config.openai_api_key()
    if not user_id:
        print("ERROR: EVAL_USER_ID not set (seed the fixture first).", file=sys.stderr)
        return 2
    if not api_key:
        print("ERROR: OPENAI_API_KEY not configured.", file=sys.stderr)
        return 2

    lf = Langfuse()
    if not lf.auth_check():
        print("ERROR: Langfuse auth failed — check keys / LANGFUSE_HOST.", file=sys.stderr)
        return 2

    items = run_eval.load_dataset()
    print(f"Syncing {len(items)} items to Langfuse dataset '{DATASET_NAME}'…")
    sync_dataset(lf, items)

    dataset = lf.get_dataset(DATASET_NAME)
    print(f"Running experiment over {len(dataset.items)} items as user {user_id}…")
    result = dataset.run_experiment(
        name="nl-sql",
        description="NL->SQL feature over the fixture library",
        task=make_task(user_id, api_key),
        evaluators=[correctness_evaluator],
        # Bounded: each task opens a NullPool DB connection + OpenAI calls; keep
        # Postgres connections and rate limits sane.
        max_concurrency=4,
    )
    lf.flush()

    print("\n" + result.format())
    if result.dataset_run_url:
        print(f"\nView in Langfuse: {result.dataset_run_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
