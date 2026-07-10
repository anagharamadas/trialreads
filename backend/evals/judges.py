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


# ── Summary judge (M3) ────────────────────────────────────────────────────
# Summaries have no single ground-truth string, so this is a reference-FREE
# rubric judge: it uses the model's own knowledge of the book to check
# faithfulness (no invented plot) and structure (three chapters covered),
# separately from the deterministic must-mention / length checks in the runner.


class SummaryVerdict(BaseModel):
    """Rubric judgement of one book summary."""

    faithful: bool = Field(
        description="True if the summary has no invented plot points or facts "
        "that contradict the actual book; minor omissions are fine."
    )
    covers_three_chapters: bool = Field(
        description="True if the summary distinctly covers the first three chapters."
    )
    score: float = Field(description="0.0-1.0 overall quality of the summary.")
    rationale: str = Field(description="One sentence explaining the verdict.")


_SUMMARY_SYSTEM = (
    "You are a strict evaluator of book summaries. You are given a BOOK title and "
    "AUTHOR, and a SUMMARY the system produced of the book's first three chapters. "
    "Using your own knowledge of the book, judge:\n"
    "- faithful: does the summary avoid invented or contradictory plot points? "
    "(Missing detail is acceptable; fabrication is not.)\n"
    "- covers_three_chapters: does it distinctly summarise the first three "
    "chapters (not one blurred blob, not just chapter one)?\n"
    "- score: overall 0.0-1.0.\n"
    "If you are not familiar with the book, judge faithful=true unless the "
    "summary is internally incoherent, and say so in the rationale."
)

_summary_chain = None


def _summary_judge_chain():
    global _summary_chain
    if _summary_chain is None:
        llm = ChatOpenAI(
            model=config.JUDGE_MODEL,
            temperature=0,
            openai_api_key=config.openai_api_key(),
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", _SUMMARY_SYSTEM),
                ("human", "BOOK: {book}\nAUTHOR: {author}\n\nSUMMARY:\n{summary}"),
            ]
        )
        _summary_chain = prompt | llm.with_structured_output(SummaryVerdict)
    return _summary_chain


def judge_summary(book: str, author: str, summary: str) -> SummaryVerdict:
    """Rubric-score one book summary (faithfulness + chapter coverage)."""
    return _summary_judge_chain().invoke(
        {"book": book, "author": author or "(unknown)", "summary": summary or "(empty)"}
    )


# ── Recommendation judge (M3) ─────────────────────────────────────────────
# Relevance is the point of a recommender, so this judge decides whether the
# recommended books genuinely suit someone who liked the seed book (genre,
# theme, appeal) — separate from the deterministic count/field checks.


class RecommendVerdict(BaseModel):
    """Judgement of a set of book recommendations against the seed book."""

    relevant: bool = Field(
        description="True if MOST recommendations genuinely suit a reader who "
        "liked the seed book (similar genre / theme / appeal)."
    )
    score: float = Field(description="0.0-1.0 overall relevance of the set.")
    rationale: str = Field(description="One sentence explaining the verdict.")


_RECOMMEND_SYSTEM = (
    "You evaluate a book recommender. You are given a SEED book (title + author) "
    "and a list of RECOMMENDED books (title by author, with a reason). Judge "
    "whether the recommendations genuinely suit a reader who liked the seed — "
    "similar genre, theme, tone, or appeal.\n"
    "- relevant: true if MOST recommendations are on-target for the seed.\n"
    "- A set from a clearly unrelated genre (e.g. physics texts for a romance "
    "novel) is NOT relevant.\n"
    "- The seed book itself must not appear in the recommendations.\n"
    "- score: overall 0.0-1.0."
)

_recommend_chain = None


def _recommend_judge_chain():
    global _recommend_chain
    if _recommend_chain is None:
        llm = ChatOpenAI(
            model=config.JUDGE_MODEL,
            temperature=0,
            openai_api_key=config.openai_api_key(),
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", _RECOMMEND_SYSTEM),
                (
                    "human",
                    "SEED: {book} by {author}\n\nRECOMMENDED:\n{recommendations}",
                ),
            ]
        )
        _recommend_chain = prompt | llm.with_structured_output(RecommendVerdict)
    return _recommend_chain


def judge_recommendations(book: str, author: str, recommendations: str) -> RecommendVerdict:
    """Score a set of recommendations for relevance to the seed book."""
    return _recommend_judge_chain().invoke(
        {
            "book": book,
            "author": author or "(unknown)",
            "recommendations": recommendations or "(none)",
        }
    )
