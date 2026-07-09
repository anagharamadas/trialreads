"""LLM-as-judge scorers for the eval harness.

Deterministic checks catch structural failures (no SQL generated, an error), but
the NL->SQL feature returns a *natural-language* answer ("You've finished 6
books."), so correctness against a short expected answer ("6") needs semantic
judgement. That is the judge's job: it is told the question, the expected answer,
and the model's actual answer, and returns a strict correct/incorrect verdict
with a rationale.

Uses the same stack the features use — langchain_openai + structured output —
so there is one OpenAI dependency across the whole codebase.
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from evals import config


class Verdict(BaseModel):
    """A single judged result."""

    correct: bool = Field(description="True only if the answer is factually correct.")
    score: float = Field(description="0.0-1.0 quality score; 1.0 = fully correct.")
    rationale: str = Field(description="One sentence explaining the verdict.")


_SYSTEM = (
    "You are a strict evaluator for a natural-language-to-SQL feature over a "
    "personal book library. You are given a QUESTION, the EXPECTED answer, and "
    "the ACTUAL answer produced by the system. Judge ONLY whether the ACTUAL "
    "answer conveys the same facts as the EXPECTED answer.\n"
    "- Ignore wording, formatting, and extra politeness; a natural-language "
    "answer that contains the expected fact is correct.\n"
    "- Numbers must match exactly. Book titles and author names must match "
    "(minor punctuation/case differences are fine).\n"
    "- If the expected answer lists several items, ALL must be present and no "
    "wrong ones added.\n"
    "- If the actual answer is empty, an error, or hedges without giving the "
    "fact, it is incorrect.\n"
    "Set score to 1.0 for correct, 0.0 for clearly wrong, and a value in "
    "between only for partially-correct list answers."
)

_judge_chain = None


def _chain():
    """Build the judge chain once (temp 0 for reproducible verdicts)."""
    global _judge_chain
    if _judge_chain is None:
        llm = ChatOpenAI(
            model=config.JUDGE_MODEL,
            temperature=0,
            openai_api_key=config.openai_api_key(),
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", _SYSTEM),
                (
                    "human",
                    "QUESTION:\n{question}\n\n"
                    "EXPECTED:\n{expected}\n\n"
                    "ACTUAL:\n{actual}",
                ),
            ]
        )
        _judge_chain = prompt | llm.with_structured_output(Verdict)
    return _judge_chain


def judge_answer(question: str, expected: str, actual: str) -> Verdict:
    """Score one NL->SQL answer against its expected answer."""
    return _chain().invoke(
        {"question": question, "expected": expected, "actual": actual or "(no answer)"}
    )
