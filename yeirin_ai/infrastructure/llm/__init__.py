"""LLM infrastructure.

Provides OpenAI-based AI features.
"""

from yeirin_ai.infrastructure.llm.document_summarizer import DocumentSummarizerClient
from yeirin_ai.infrastructure.llm.openai_client import OpenAIRecommendationClient
from yeirin_ai.infrastructure.llm.recommender_opinion_generator import (
    ChildContext,
    RecommenderOpinion,
    RecommenderOpinionGenerator,
)

__all__ = [
    "DocumentSummarizerClient",
    "OpenAIRecommendationClient",
    "RecommenderOpinionGenerator",
    "RecommenderOpinion",
    "ChildContext",
]
