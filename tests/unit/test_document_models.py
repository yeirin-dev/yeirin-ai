"""문서 처리 도메인 모델 테스트."""

import pytest
from pydantic import ValidationError

from yeirin_ai.domain.document.models import (
    DocumentSummary,
    DocumentType,
    SummaryRequest,
)


class TestDocumentType:
    """DocumentType enum 테스트."""

    def test_KPRC_REPORT_값이_올바르다(self) -> None:
        """KPRC_REPORT enum 값이 올바르다."""
        assert DocumentType.KPRC_REPORT.value == "kprc_report"

    def test_COUNSEL_REQUEST_값이_올바르다(self) -> None:
        """COUNSEL_REQUEST enum 값이 올바르다."""
        assert DocumentType.COUNSEL_REQUEST.value == "counsel_request"

    def test_COUNSEL_REPORT_값이_올바르다(self) -> None:
        """COUNSEL_REPORT enum 값이 올바르다."""
        assert DocumentType.COUNSEL_REPORT.value == "counsel_report"

    def test_OTHER_값이_올바르다(self) -> None:
        """OTHER enum 값이 올바르다."""
        assert DocumentType.OTHER.value == "other"


class TestSummaryRequest:
    """SummaryRequest 모델 테스트."""

    def test_기본값으로_요청을_생성한다(self) -> None:
        """기본값으로 요청을 생성할 수 있다."""
        request = SummaryRequest()

        assert request.document_type == DocumentType.KPRC_REPORT
        assert request.child_name is None
        assert request.include_recommendations is True

    def test_모든_필드를_지정하여_요청을_생성한다(self) -> None:
        """모든 필드를 지정하여 요청을 생성할 수 있다."""
        request = SummaryRequest(
            document_type=DocumentType.COUNSEL_REPORT,
            child_name="홍길동",
            include_recommendations=False,
        )

        assert request.document_type == DocumentType.COUNSEL_REPORT
        assert request.child_name == "홍길동"
        assert request.include_recommendations is False


class TestDocumentSummary:
    """DocumentSummary 모델 테스트."""

    def test_올바른_데이터로_요약을_생성한다(self) -> None:
        """올바른 데이터로 요약을 생성할 수 있다."""
        summary = DocumentSummary(
            document_type=DocumentType.KPRC_REPORT,
            summary_lines=[
                "아동은 전반적으로 정상 발달 범위 내에 있습니다.",
                "주의력 영역에서 다소 낮은 점수를 보이고 있습니다.",
                "사회성 발달은 양호한 수준입니다.",
            ],
            expert_opinion="본 검사 결과, 아동은 전반적으로 정상 발달 범위 내에 있으나...",
            key_findings=["주의력 영역 저하", "사회성 양호"],
            recommendations=["집중력 훈련 권장", "사회활동 장려"],
            confidence_score=0.85,
        )

        assert summary.document_type == DocumentType.KPRC_REPORT
        assert len(summary.summary_lines) == 3
        assert summary.confidence_score == 0.85

    def test_요약_문장은_최소_1개가_필요하다(self) -> None:
        """요약 문장은 최소 1개가 필요하다."""
        with pytest.raises(ValidationError):
            DocumentSummary(
                document_type=DocumentType.KPRC_REPORT,
                summary_lines=[],
                expert_opinion="전문가 소견",
            )

    def test_요약_문장은_최대_5개까지_허용된다(self) -> None:
        """요약 문장은 최대 5개까지 허용된다."""
        with pytest.raises(ValidationError):
            DocumentSummary(
                document_type=DocumentType.KPRC_REPORT,
                summary_lines=["1", "2", "3", "4", "5", "6"],
                expert_opinion="전문가 소견",
            )

    def test_신뢰도_점수는_0과_1_사이여야_한다(self) -> None:
        """신뢰도 점수는 0.0~1.0 범위여야 한다."""
        # 정상 케이스
        summary = DocumentSummary(
            document_type=DocumentType.KPRC_REPORT,
            summary_lines=["요약"],
            expert_opinion="소견",
            confidence_score=0.5,
        )
        assert summary.confidence_score == 0.5

        # 범위 초과
        with pytest.raises(ValidationError):
            DocumentSummary(
                document_type=DocumentType.KPRC_REPORT,
                summary_lines=["요약"],
                expert_opinion="소견",
                confidence_score=1.5,
            )

    def test_기본값이_올바르게_설정된다(self) -> None:
        """기본값이 올바르게 설정된다."""
        summary = DocumentSummary(
            document_type=DocumentType.KPRC_REPORT,
            summary_lines=["요약"],
            expert_opinion="소견",
        )

        assert summary.key_findings == []
        assert summary.recommendations == []
        assert summary.confidence_score == 0.0
