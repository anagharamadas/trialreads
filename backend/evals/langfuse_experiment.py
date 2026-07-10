"""M2: run the NL->SQL eval as a Langfuse dataset experiment.

Where M1 (`run_eval.py`) scores locally and writes a Markdown report, this pushes
the SAME golden set to a Langfuse **dataset** and runs an **experiment**, so every
run's scores + traces land in the Langfuse UI for comparison over time. It reuses
the M1 assets unchanged: the fixture-seeded `EVAL_USER_ID`, `datasets/nl_sql.jsonl`,
and the LLM judge in `judges.py`. The Langfuse plumbing lives in `_experiment.py`,
shared with the other feature runners; this file is just NL->SQL's task, evaluator,
and item mapping.

    cd backend
    python -m evals.langfuse_experiment

Needs LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY (+ EVAL_USER_ID and a seeded
fixture) in backend/.env.
"""

import sys

from langfuse.experiment import Evaluation

from app.services import library_query

from evals import _experiment, config, judges, run_eval

DATASET_NAME = "nl-sql-golden"


def build_items() -> list[dict]:
    """Normalise the golden jsonl into Langfuse dataset items."""
    return [
        {
            "id": it["id"],
            "input": it["question"],
            "expected_output": str(it["expected"]),
            "metadata": {"checks": it.get("checks", {}), "note": it.get("note")},
        }
        for it in run_eval.load_dataset()
    ]


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
    user_id = config.eval_user_id()
    if not user_id:
        print("ERROR: EVAL_USER_ID not set (seed the fixture first).", file=sys.stderr)
        return 2
    return _experiment.run_experiment(
        name="nl-sql",
        description="NL->SQL feature over the fixture library",
        langfuse_dataset=DATASET_NAME,
        items=build_items(),
        task=make_task(user_id, config.openai_api_key()),
        evaluator=correctness_evaluator,
    )


if __name__ == "__main__":
    raise SystemExit(main())
