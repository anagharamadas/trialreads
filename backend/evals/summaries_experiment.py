"""M3: evaluate the book summariser as a Langfuse dataset experiment.

Unlike NL->SQL, a summary has no single ground-truth string, so scoring is
multi-dimensional and mostly reference-free:

  deterministic (in this file):
    - length_ok         summary reaches the expected word count
    - mentions_covered  fraction of must-mention facts (names/places from the
                        opening chapters) present in the summary
  rubric judge (judges.judge_summary, uses the model's own knowledge):
    - faithful          no invented / contradictory plot points
    - covers_3_chapters distinctly summarises the first three chapters
    - quality           overall 0-1

An item passes only if length_ok AND all must-mentions present AND faithful AND
covers_three_chapters. Shares the Langfuse plumbing in `_experiment.py`.

    cd backend
    python -m evals.summaries_experiment
"""

from langfuse.experiment import Evaluation

from app.services import summariser

from evals import _experiment, config, judges, run_eval

DATASET_NAME = "summaries-golden"


def build_items() -> list[dict]:
    items = []
    for it in run_eval.load_dataset("summaries.jsonl"):
        facts = it.get("must_mention", []) or []
        items.append(
            {
                "id": it["id"],
                "input": it["book"],
                "expected_output": "Faithful summary of the first 3 chapters mentioning: "
                + ", ".join(facts),
                "metadata": {
                    "author": it.get("author", ""),
                    "must_mention": facts,
                    "checks": it.get("checks", {}),
                    "note": it.get("note"),
                    # For the negative control, the book actually summarised differs
                    # from `input` (the book the judge is told about). Positive items
                    # summarise the same book they claim.
                    "summarise_book": it.get("summarise_book", it["book"]),
                    "summarise_author": it.get("summarise_author", it.get("author", "")),
                },
            }
        )
    return items


def make_task(api_key: str, user_id: str):
    def task(*, item, **kwargs):
        meta = item.metadata or {}
        # Summarise `summarise_book` (== the claimed book for positive items; a
        # DIFFERENT book for the negative control), so the judge — told about
        # item.input — can catch the mismatch.
        book = meta.get("summarise_book") or item.input
        author = meta.get("summarise_author", "")
        return summariser.get_summary(book, author, api_key, user_id)

    return task


def summary_evaluator(*, input, output, expected_output=None, metadata=None, **kwargs):
    meta = metadata or {}
    author = meta.get("author", "")
    must = meta.get("must_mention", []) or []
    checks = meta.get("checks", {}) or {}
    summary = output if isinstance(output, str) else str(output or "")

    # ── Deterministic checks ─────────────────────────────────────────────
    words = len(summary.split())
    min_words = checks.get("min_words", 300)
    length_ok = words >= min_words
    low = summary.lower()
    present = [f for f in must if f.lower() in low]
    coverage = len(present) / len(must) if must else 1.0
    mentions_all = coverage == 1.0

    # ── Rubric judge ─────────────────────────────────────────────────────
    verdict = judges.judge_summary(input, author, summary)

    evaluations = [
        Evaluation(
            name="quality", value=float(verdict.score),
            comment=verdict.rationale, data_type="NUMERIC",
        ),
        Evaluation(name="faithful", value=bool(verdict.faithful), data_type="BOOLEAN"),
        Evaluation(
            name="covers_3_chapters",
            value=bool(verdict.covers_three_chapters), data_type="BOOLEAN",
        ),
        Evaluation(
            name="mentions_covered", value=float(coverage), data_type="NUMERIC",
            comment=f"{len(present)}/{len(must)} present: {present}",
        ),
        Evaluation(
            name="length_ok", value=bool(length_ok), data_type="BOOLEAN",
            comment=f"{words} words (min {min_words})",
        ),
    ]
    # Negative control (expect_unfaithful): the summary is of a DIFFERENT book
    # than item.input, so the item passes only if the judge flags it unfaithful.
    # Guards against a rubber-stamp faithfulness judge.
    negative_control = bool(checks.get("expect_unfaithful"))
    if negative_control:
        passed = not verdict.faithful
    else:
        passed = (
            length_ok
            and mentions_all
            and verdict.faithful
            and verdict.covers_three_chapters
        )
    evaluations.append(
        Evaluation(
            name="passed",
            value=bool(passed),
            data_type="BOOLEAN",
            comment="negative control (judge must flag unfaithful)"
            if negative_control
            else None,
        )
    )
    return evaluations


def main() -> int:
    return _experiment.run_experiment(
        name="summaries",
        description="Book summariser — first 3 chapters, faithfulness + coverage",
        langfuse_dataset=DATASET_NAME,
        items=build_items(),
        task=make_task(config.openai_api_key(), config.eval_user_id()),
        evaluator=summary_evaluator,
    )


if __name__ == "__main__":
    raise SystemExit(main())
