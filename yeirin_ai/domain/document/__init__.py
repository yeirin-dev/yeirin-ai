"""문서 처리 도메인.

PDF 요약 및 첨삭 기능을 위한 도메인 모델을 정의합니다.
"""

from yeirin_ai.domain.document.models import (
    DocumentSummary,
    DocumentType,
    SummaryRequest,
)

__all__ = [
    "DocumentSummary",
    "DocumentType",
    "SummaryRequest",
]
