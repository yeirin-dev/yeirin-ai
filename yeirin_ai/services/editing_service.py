"""문서 첨삭 서비스.

추후 구현 예정: 상담 보고서 첨삭 기능을 제공합니다.
기획 확정 후 구체적인 로직을 구현합니다.
"""

# TODO: 기획 확정 후 구현 예정
#
# 예상 기능:
# - 문법 교정
# - 문체 개선 (전문적인 어조로 변환)
# - 전문 용어 교정 (심리상담 용어 표준화)
# - 종합 첨삭 (위 기능 통합)
#
# 구현 방향:
# - OpenAI GPT-4o를 활용한 첨삭 로직
# - 원본과 수정본 비교 (diff) 기능
# - 수정 이유 설명 제공
# - 선택적 수정 적용 기능


class EditingServiceError(Exception):
    """첨삭 서비스 에러."""

    pass


class EditingService:
    """문서 첨삭 서비스.

    TODO: 기획 확정 후 구현 예정
    """

    def __init__(self) -> None:
        """서비스를 초기화합니다."""
        pass

    async def edit_document(self, text_content: str) -> dict:
        """문서를 첨삭합니다.

        TODO: 기획 확정 후 구현 예정

        Args:
            text_content: 첨삭할 텍스트

        Returns:
            첨삭 결과

        Raises:
            NotImplementedError: 아직 구현되지 않음
        """
        raise NotImplementedError("첨삭 기능은 기획 확정 후 구현 예정입니다")
