"""Langfuse LLM observability (Phase 3, M5) — enabled only when keys are set.

Langfuse v4 (OTel-based SDK). Integration style per current Langfuse docs for
LangChain/LangGraph: pass `langfuse.langchain.CallbackHandler` in the per-call
config, with user_id / tags via the documented `langfuse_*` metadata keys.

Client configuration comes from env vars read by the SDK itself:
    LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY
    LANGFUSE_BASE_URL              (https://cloud.langfuse.com)
    LANGFUSE_TRACING_ENVIRONMENT   (local | production)

Without the keys, `langchain_config()` returns {} and nothing Langfuse-related
is ever imported — zero behavioural or latency change.

The LlamaIndex NL→SQL path is NOT instrumented here: Langfuse's current
recommendation for LlamaIndex is OpenInference instrumentation
(openinference-instrumentation-llama-index), which registers against the global
OpenTelemetry tracer provider that telemetry.py already owns for Grafana Cloud.
Wiring the two together safely needs live keys to test against — see
OBSERVABILITY.md, "Langfuse: LlamaIndex follow-up".
"""

import logging
import os

from opentelemetry import trace

logger = logging.getLogger(__name__)


def enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def langchain_config(feature: str, user_id: str = "") -> dict:
    """Per-invocation LangChain config that routes the run to Langfuse.

    Merge into `.invoke(..., config={...})`. `feature` becomes a Langfuse tag
    (one of: summarise, nl-sql, curate, recommend) so cost can be answered
    per feature. The active OTel trace_id is attached as metadata + tag, so a
    slow trace found in Grafana can be looked up directly in Langfuse.
    """
    if not enabled():
        return {}
    try:
        from langfuse.langchain import CallbackHandler
    except Exception:  # never let observability break a paid user request
        logger.exception("Langfuse import failed; continuing without it")
        return {}

    metadata: dict = {"langfuse_tags": [feature]}
    if user_id:
        metadata["langfuse_user_id"] = user_id
    ctx = trace.get_current_span().get_span_context()
    if ctx.is_valid:
        otel_trace_id = format(ctx.trace_id, "032x")
        metadata["otel_trace_id"] = otel_trace_id
        # Grafana→Langfuse jump: copy the trace id from Tempo and search
        # Langfuse for the tag "otel:<trace_id>".
        metadata["langfuse_tags"] = [feature, f"otel:{otel_trace_id}"]

    return {"callbacks": [CallbackHandler()], "metadata": metadata}
