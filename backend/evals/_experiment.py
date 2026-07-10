"""Shared Langfuse dataset-experiment machinery (used by every feature runner).

Each feature (nl-sql, summaries, …) supplies three things — a normalised item
list, a `task` that runs the real feature, and an `evaluator` that scores one
output — and this module handles the rest: guards, auth, idempotent dataset
upsert, `run_experiment`, flush, and printing the dataset-run URL.

A normalised item is a dict: {"id", "input", "expected_output", "metadata"}.
The Langfuse DatasetItem the task/evaluator receive exposes those as
`.input` / `.expected_output` / `.metadata`.
"""

import sys

from langfuse import Langfuse

from app import llm_observability

from evals import config


def _sync_dataset(lf: Langfuse, name: str, description: str, items: list[dict]) -> None:
    """Upsert items into a Langfuse dataset (idempotent via stable id)."""
    lf.create_dataset(name=name, description=description)
    for it in items:
        lf.create_dataset_item(
            dataset_name=name,
            id=it["id"],
            input=it.get("input"),
            expected_output=it.get("expected_output"),
            metadata=it.get("metadata"),
        )


def run_experiment(
    *,
    name: str,
    description: str,
    langfuse_dataset: str,
    items: list[dict],
    task,
    evaluator,
    max_concurrency: int = 4,
) -> int:
    """Sync `items` to a Langfuse dataset and run `task`+`evaluator` over them.

    Returns a process exit code (0 ok, 2 on a config/guard failure). Feature-
    specific guards (e.g. EVAL_USER_ID) belong in the caller, before this runs.
    """
    if not llm_observability.enabled():
        print(
            "ERROR: Langfuse keys not set. Add LANGFUSE_PUBLIC_KEY / "
            "LANGFUSE_SECRET_KEY to backend/.env.",
            file=sys.stderr,
        )
        return 2
    if not config.openai_api_key():
        print("ERROR: OPENAI_API_KEY not configured.", file=sys.stderr)
        return 2

    lf = Langfuse()
    if not lf.auth_check():
        print("ERROR: Langfuse auth failed — check keys / LANGFUSE_HOST.", file=sys.stderr)
        return 2

    print(f"Syncing {len(items)} items to Langfuse dataset '{langfuse_dataset}'…")
    _sync_dataset(lf, langfuse_dataset, description, items)

    dataset = lf.get_dataset(langfuse_dataset)
    print(f"Running experiment '{name}' over {len(dataset.items)} items…")
    result = dataset.run_experiment(
        name=name,
        description=description,
        task=task,
        evaluators=[evaluator],
        max_concurrency=max_concurrency,
    )
    lf.flush()

    print("\n" + result.format())
    if result.dataset_run_url:
        print(f"\nView in Langfuse: {result.dataset_run_url}")
    return 0
