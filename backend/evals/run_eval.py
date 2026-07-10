"""Run the NL->SQL golden dataset over the fixture and score every answer.

    cd backend
    python -m evals.run_eval

For each dataset item it calls the REAL feature function
(app.services.library_query.answer_query) as EVAL_USER_ID, applies the
deterministic checks declared on the item, runs the LLM judge, and records the
result. At the end it writes a Markdown report and exits non-zero if the pass
rate is below EVAL_PASS_THRESHOLD (so CI can gate on it later).

No Langfuse here by design (M1). record_result() is the single seam an M2
Langfuse sink hooks into — keep result construction going through it.
"""

import json
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.services import library_query

from evals import config, judges


@dataclass
class Result:
    id: str
    question: str
    expected: str
    actual: str = ""
    sql: str | None = None
    passed: bool = False
    score: float = 0.0
    rationale: str = ""
    checks: dict = field(default_factory=dict)  # check name -> passed bool
    error: str = ""
    negative_control: bool = False  # item passes when the judge REJECTS the answer


# Collected results for the report. record_result() is the seam where M2 will
# also push to Langfuse (dataset run + score); today it only accumulates locally.
_results: list[Result] = []


def record_result(result: Result) -> None:
    _results.append(result)
    status = "PASS" if result.passed else "FAIL"
    detail = result.error or result.rationale
    print(f"  [{status}] {result.id}  score={result.score:.2f}  {detail}")


def load_dataset(name: str = "nl_sql.jsonl") -> list[dict]:
    path = config.DATASETS_DIR / name
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_item(item: dict, user_id: str, api_key: str) -> Result:
    result = Result(
        id=item["id"], question=item["question"], expected=str(item["expected"])
    )
    checks = item.get("checks", {})

    try:
        out = library_query.answer_query(item["question"], user_id, api_key)
        result.actual = out.get("answer", "")
        result.sql = out.get("sql")
    except Exception as exc:  # a feature crash is a failed eval, not a crashed run
        result.error = f"answer_query raised: {exc.__class__.__name__}: {exc}"
        result.checks = {"no_exception": False}
        return result

    # ── Deterministic structural checks ──────────────────────────────────
    result.checks["no_exception"] = True
    if checks.get("sql_required"):
        result.checks["sql_generated"] = bool(result.sql)

    # ── LLM-as-judge correctness ─────────────────────────────────────────
    judge_ran = False
    judged_correct = False
    try:
        verdict = judges.judge_answer(result.question, result.expected, result.actual)
        result.score = verdict.score
        result.rationale = verdict.rationale
        judged_correct = verdict.correct
        judge_ran = True
    except Exception as exc:
        result.error = f"judge raised: {exc.__class__.__name__}: {exc}"

    # Negative control (expect_incorrect): `expected` is a deliberately WRONG
    # answer, and the item passes only if the judge actually ran and flagged the
    # (correct) actual answer as NOT matching it — i.e. the judge isn't a
    # rubber stamp. A judge crash must never masquerade as a passing control,
    # hence the explicit judge_ran gate on both paths.
    result.negative_control = bool(checks.get("expect_incorrect"))
    structural_ok = all(result.checks.values())
    if result.negative_control:
        result.passed = structural_ok and judge_ran and not judged_correct
    else:
        result.passed = structural_ok and judge_ran and judged_correct
    return result


def write_report(user_id: str, dataset_name: str) -> None:
    total = len(_results)
    passed = sum(r.passed for r in _results)
    rate = passed / total if total else 0.0
    # Avg judge score reflects answer quality on POSITIVE items only. Negative
    # controls score ~0 by design (a correct rejection), so averaging them in
    # would understate quality.
    positives = [r for r in _results if not r.negative_control]
    n_controls = total - len(positives)
    avg_score = sum(r.score for r in positives) / len(positives) if positives else 0.0
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    lines = [
        "# NL->SQL eval report",
        "",
        f"- **Run:** {stamp}",
        f"- **Dataset:** `{dataset_name}` ({total} items, "
        f"{len(positives)} positive + {n_controls} negative-control)",
        f"- **Judge model:** `{config.JUDGE_MODEL}`",
        f"- **Fixture user:** `{user_id}`",
        f"- **Pass rate:** {passed}/{total} = **{rate:.0%}** "
        f"(threshold {config.PASS_THRESHOLD:.0%})",
        f"- **Avg judge score (positives):** {avg_score:.2f}",
        "",
        "| id | result | score | question | expected | actual | note |",
        "|----|--------|-------|----------|----------|--------|------|",
    ]
    for r in _results:
        note = r.error or r.rationale
        if r.negative_control:
            note = f"[neg-control] {note}"
        actual = (r.actual or "").replace("\n", " ")
        if len(actual) > 80:
            actual = actual[:77] + "..."
        lines.append(
            f"| {r.id} | {'✅' if r.passed else '❌'} | {r.score:.2f} "
            f"| {r.question} | {r.expected} | {actual} | {note} |"
        )
    lines.append("")

    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = config.REPORTS_DIR / dataset_name.replace(".jsonl", ".md")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {report_path}")


def main() -> int:
    user_id = config.eval_user_id()
    api_key = config.openai_api_key()
    if not user_id:
        print(
            "ERROR: EVAL_USER_ID is not set. Add it to backend/.env (a throwaway\n"
            "auth user's UUID) and seed the fixture:  python -m evals.seed_fixture",
            file=sys.stderr,
        )
        return 2
    if not api_key:
        print("ERROR: OPENAI_API_KEY is not configured in backend/.env.", file=sys.stderr)
        return 2

    dataset_name = "nl_sql.jsonl"
    try:
        items = load_dataset(dataset_name)
    except FileNotFoundError:
        print(f"ERROR: dataset {dataset_name} not found.", file=sys.stderr)
        return 2

    print(f"Running {len(items)} NL->SQL eval item(s) as user {user_id}\n")
    for item in items:
        try:
            record_result(run_item(item, user_id, api_key))
        except Exception:  # never let one item abort the whole run
            traceback.print_exc()
            record_result(
                Result(
                    id=item.get("id", "?"),
                    question=item.get("question", ""),
                    expected=str(item.get("expected", "")),
                    error="unexpected harness error (see traceback above)",
                )
            )

    write_report(user_id, dataset_name)

    passed = sum(r.passed for r in _results)
    rate = passed / len(_results) if _results else 0.0
    print(f"Pass rate: {passed}/{len(_results)} = {rate:.0%}")
    return 0 if rate >= config.PASS_THRESHOLD else 1


if __name__ == "__main__":
    raise SystemExit(main())
