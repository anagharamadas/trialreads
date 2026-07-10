"""M3: evaluate the book recommender as a Langfuse dataset experiment.

Scoring combines deterministic structure with a relevance judge:

  deterministic (in this file):
    - count_ok       exactly `expect_count` (5) recommendations parsed
    - fields_ok      every recommendation has a title AND an author
    - seed_excluded  the seed book is not recommended back to the user
  relevance judge (judges.judge_recommendations):
    - relevant       do the recommendations genuinely suit the seed's reader?
    - relevance      overall 0-1

A positive item passes only if the structure holds AND the set is relevant. The
negative control (`checks.expect_irrelevant`) generates recommendations for a
DIFFERENT (unrelated-genre) book than the judge is told the seed is, and passes
only if the judge flags the set irrelevant — guarding the relevance judge.

    cd backend
    python -m evals.recommend_experiment
"""

from langfuse.experiment import Evaluation

from app.services import recommendations

from evals import _experiment, config, judges, run_eval

DATASET_NAME = "recommend-golden"


def build_items() -> list[dict]:
    items = []
    for it in run_eval.load_dataset("recommend.jsonl"):
        items.append(
            {
                "id": it["id"],
                "input": it["book"],
                "expected_output": f"5 books relevant to '{it['book']}' by {it.get('author', '')}",
                "metadata": {
                    "author": it.get("author", ""),
                    "checks": it.get("checks", {}),
                    "note": it.get("note"),
                    # Negative control recommends for a different, unrelated book
                    # than the judge is told; positive items use the seed itself.
                    "recommend_for_book": it.get("recommend_for_book", it["book"]),
                    "recommend_for_author": it.get("recommend_for_author", it.get("author", "")),
                },
            }
        )
    return items


def make_task(api_key: str, user_id: str):
    def task(*, item, **kwargs):
        meta = item.metadata or {}
        book = meta.get("recommend_for_book") or item.input
        author = meta.get("recommend_for_author", "")
        return recommendations.recommend(book, author, api_key, user_id)

    return task


def _format_recs(recs: list[dict]) -> str:
    return "\n".join(
        f"{i}. {r.get('title', '?')} by {r.get('author', '?')} — {r.get('reason', '')}"
        for i, r in enumerate(recs, 1)
    )


def recommend_evaluator(*, input, output, expected_output=None, metadata=None, **kwargs):
    meta = metadata or {}
    author = meta.get("author", "")
    checks = meta.get("checks", {}) or {}
    recs = output.get("recommendations", []) if isinstance(output, dict) else []

    # ── Deterministic structure ──────────────────────────────────────────
    expect_count = checks.get("expect_count", 5)
    count_ok = len(recs) == expect_count
    fields_ok = bool(recs) and all(r.get("title") and r.get("author") for r in recs)
    seed_lower = input.strip().lower()
    seed_excluded = all((r.get("title") or "").strip().lower() != seed_lower for r in recs)

    # ── Relevance judge ──────────────────────────────────────────────────
    verdict = judges.judge_recommendations(input, author, _format_recs(recs))

    evaluations = [
        Evaluation(
            name="relevance", value=float(verdict.score),
            comment=verdict.rationale, data_type="NUMERIC",
        ),
        Evaluation(name="relevant", value=bool(verdict.relevant), data_type="BOOLEAN"),
        Evaluation(
            name="count_ok", value=bool(count_ok), data_type="BOOLEAN",
            comment=f"{len(recs)} of {expect_count}",
        ),
        Evaluation(name="fields_ok", value=bool(fields_ok), data_type="BOOLEAN"),
        Evaluation(name="seed_excluded", value=bool(seed_excluded), data_type="BOOLEAN"),
    ]

    negative_control = bool(checks.get("expect_irrelevant"))
    if negative_control:
        passed = count_ok and fields_ok and not verdict.relevant
    else:
        passed = count_ok and fields_ok and seed_excluded and verdict.relevant
    evaluations.append(
        Evaluation(
            name="passed", value=bool(passed), data_type="BOOLEAN",
            comment="negative control (judge must flag irrelevant)"
            if negative_control
            else None,
        )
    )
    return evaluations


def main() -> int:
    return _experiment.run_experiment(
        name="recommend",
        description="Book recommender — 5 relevant similar books",
        langfuse_dataset=DATASET_NAME,
        items=build_items(),
        task=make_task(config.openai_api_key(), config.eval_user_id()),
        evaluator=recommend_evaluator,
    )


if __name__ == "__main__":
    raise SystemExit(main())
