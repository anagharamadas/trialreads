"""AI endpoints: /summarise and /recommend (JWT-guarded).

These don't touch the library table — they just call OpenAI. The user_id
dependency is present so the endpoints require a valid token (and so we can add
per-user rate limiting in M6).
"""

from fastapi import APIRouter, Depends

from ..config import get_settings
from ..rate_limit import rate_limited_user
from ..schemas import (
    Recommendation,
    RecommendRequest,
    RecommendResponse,
    SummariseRequest,
    SummariseResponse,
)
from ..services import recommendations, summariser

router = APIRouter(tags=["ai"])
settings = get_settings()


@router.post("/summarise", response_model=SummariseResponse)
def summarise(payload: SummariseRequest, user_id: str = Depends(rate_limited_user)):
    text = summariser.get_summary(
        payload.book_name, payload.author_name or "", settings.openai_api_key, user_id
    )
    return SummariseResponse(summary=text)


@router.post("/recommend", response_model=RecommendResponse)
def recommend(payload: RecommendRequest, user_id: str = Depends(rate_limited_user)):
    result = recommendations.recommend(
        payload.book_name, payload.author_name or "", settings.openai_api_key, user_id
    )
    recs = [Recommendation(**r) for r in result["recommendations"]]
    return RecommendResponse(original_response=result["original_response"], recommendations=recs)
