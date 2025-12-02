"""문서 첨삭 도메인 모델.

추후 구현 예정: 상담 보고서 첨삭 기능을 위한 도메인 모델입니다.
기획 확정 후 구체적인 모델을 정의합니다.
"""

from enum import Enum

from pydantic import BaseModel, Field


class EditingType(str, Enum):
    """첨삭 유형."""

    GRAMMAR = "grammar"  # 문법 교정
    STYLE = "style"  # 문체 개선
    PROFESSIONAL = "professional"  # 전문 용어 교정
    COMPREHENSIVE = "comprehensive"  # 종합 첨삭


class EditingSuggestion(BaseModel):
    """개별 첨삭 제안.

    TODO: 기획 확정 후 구체화 필요
    """

    original_text: str = Field(..., description="원본 텍스트")
    suggested_text: str = Field(..., description="제안 텍스트")
    editing_type: EditingType = Field(..., description="첨삭 유형")
    reason: str = Field(..., description="수정 이유")
    position: tuple[int, int] | None = Field(
        default=None, description="원본 내 위치 (시작, 끝)"
    )


class EditingRequest(BaseModel):
    """첨삭 요청 모델.

    TODO: 기획 확정 후 구체화 필요
    """

    text_content: str = Field(..., description="첨삭할 텍스트")
    editing_types: list[EditingType] = Field(
        default=[EditingType.COMPREHENSIVE],
        description="요청 첨삭 유형",
    )


class EditingResult(BaseModel):
    """첨삭 결과 모델.

    TODO: 기획 확정 후 구체화 필요
    """

    original_text: str = Field(..., description="원본 텍스트")
    edited_text: str = Field(..., description="첨삭된 텍스트")
    suggestions: list[EditingSuggestion] = Field(
        default_factory=list,
        description="개별 첨삭 제안 목록",
    )
    total_changes: int = Field(default=0, description="총 수정 횟수")
