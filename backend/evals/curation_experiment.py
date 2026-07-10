"""M3: evaluate the shelf-curation agent as a Langfuse dataset experiment.

Curation is the agentic feature: run_curation(messages) drives a ReAct agent
(with a Google Books search tool) and returns {reply, proposal}. It has TWO
correct behaviours, and the dataset exercises both:

  expect="clarify"  a vague goal → the agent asks clarifying questions and does
                    NOT produce a list (proposal is None).
  expect="list"     a clear goal → a grounded, ordered reading list. Scored on
                    structure (has_proposal / count_ok / fields_ok / ordered) and
                    a relevance+ordering judge (judges.judge_curation).

Negative control (`checks.expect_irrelevant`): the agent is driven toward one
goal (quantum mechanics) while the judge is told a different goal (home cooking),
so a relevant-looking list must still be flagged irrelevant.

⚠️ Network-dependent + can be flaky: the agent hits the live Google Books API for
both search and grounding, which rate-limits under bursts. Runs sequentially
(max_concurrency=1); a degraded run (dropped books → small/empty proposals) may
need a re-run.

    cd backend
    python -m evals.curation_experiment
"""

from langfuse.experiment import Evaluation

from app.services import curation_agent

from evals import _experiment, config, judges, run_eval

DATASET_NAME = "curation-golden"


def build_items() -> list[dict]:
    items = []
    for it in run_eval.load_dataset("curation.jsonl"):
        items.append(
            {
                "id": it["id"],
                "input": it["goal"],
                "expected_output": it["checks"].get("expect", "list"),
                "metadata": {
                    "messages": it["messages"],
                    "checks": it.get("checks", {}),
                    "note": it.get("note"),
                },
            }
        )
    return items


def make_task(api_key: str, user_id: str):
    def task(*, item, **kwargs):
        messages = (item.metadata or {}).get("messages", [])
        try:
            return curation_agent.run_curation(messages, api_key, user_id)
        except Exception as exc:  # one agent failure shouldn't abort the run
            return {"reply": f"(error: {exc.__class__.__name__}: {exc})", "proposal": None}

    return task


def _format_list(proposal: dict) -> str:
    lines = [proposal.get("overview", "")]
    for it in proposal.get("items", []):
        lines.append(
            f"{it.get('reading_order')}. {it.get('title', '?')} "
            f"by {it.get('author', '?')} — {it.get('reason', '')}"
        )
    return "\n".join(lines)


def curation_evaluator(*, input, output, expected_output=None, metadata=None, **kwargs):
    meta = metadata or {}
    checks = meta.get("checks", {}) or {}
    expect = checks.get("expect", "list")
    reply = output.get("reply", "") if isinstance(output, dict) else ""
    proposal = output.get("proposal") if isinstance(output, dict) else None

    # ── Clarify behaviour: must ask questions, must NOT produce a list ────
    if expect == "clarify":
        no_proposal = proposal is None
        asks_question = "?" in (reply or "")
        passed = no_proposal and asks_question
        return [
            Evaluation(name="no_proposal", value=bool(no_proposal), data_type="BOOLEAN"),
            Evaluation(name="asks_question", value=bool(asks_question), data_type="BOOLEAN"),
            Evaluation(
                name="passed", value=bool(passed), data_type="BOOLEAN",
                comment="clarify item (questions, no list)",
            ),
        ]

    # ── List behaviour: grounded, well-formed, ordered, relevant ─────────
    items = (proposal or {}).get("items", []) if proposal else []
    has_proposal = proposal is not None and bool(items)
    min_items, max_items = checks.get("min_items", 3), checks.get("max_items", 10)
    count_ok = has_proposal and (min_items <= len(items) <= max_items)
    fields_ok = has_proposal and all(it.get("title") and it.get("author") for it in items)
    ordered = has_proposal and (
        [it.get("reading_order") for it in items] == list(range(1, len(items) + 1))
    )

    evaluations = [
        Evaluation(name="has_proposal", value=bool(has_proposal), data_type="BOOLEAN"),
        Evaluation(
            name="count_ok", value=bool(count_ok), data_type="BOOLEAN",
            comment=f"{len(items)} items",
        ),
        Evaluation(name="fields_ok", value=bool(fields_ok), data_type="BOOLEAN"),
        Evaluation(name="ordered", value=bool(ordered), data_type="BOOLEAN"),
    ]

    negative_control = bool(checks.get("expect_irrelevant"))
    if not has_proposal:
        # No list to judge — record and fail (a list was expected).
        evaluations.append(
            Evaluation(name="relevance", value=0.0, data_type="NUMERIC",
                       comment="no proposal produced")
        )
        evaluations.append(Evaluation(name="relevant", value=False, data_type="BOOLEAN"))
        passed = False
    else:
        verdict = judges.judge_curation(input, _format_list(proposal))
        evaluations += [
            Evaluation(name="relevance", value=float(verdict.score),
                       comment=verdict.rationale, data_type="NUMERIC"),
            Evaluation(name="relevant", value=bool(verdict.relevant), data_type="BOOLEAN"),
            Evaluation(name="well_ordered", value=bool(verdict.well_ordered),
                       data_type="BOOLEAN"),
        ]
        if negative_control:
            passed = count_ok and not verdict.relevant
        else:
            passed = count_ok and fields_ok and ordered and verdict.relevant

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
        name="curation",
        description="Shelf-curation agent — clarify vs grounded ordered reading list",
        langfuse_dataset=DATASET_NAME,
        items=build_items(),
        task=make_task(config.openai_api_key(), config.eval_user_id()),
        evaluator=curation_evaluator,
        max_concurrency=1,  # live Google Books calls rate-limit under bursts
    )


if __name__ == "__main__":
    raise SystemExit(main())
